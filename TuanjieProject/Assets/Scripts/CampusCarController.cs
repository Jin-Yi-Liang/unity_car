using System;
using System.Collections.Generic;
using System.Globalization;
using System.Net.Sockets;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;

public sealed class CampusCarController : MonoBehaviour {
 [SerializeField] TextAsset graphAsset;
 [SerializeField] float speedMetresPerSecond=12f;
 [SerializeField] float obstacleDistance=2f;
 [SerializeField] Vector3 initialForward=new Vector3(-0.99993f,0,0.01176f);
 SimulationGraph graph;
 TcpClient client;
 Task connectTask;
 readonly StringBuilder incoming=new StringBuilder();
 readonly byte[] bytes=new byte[4096];
 readonly List<Vector2> route=new List<Vector2>();
 Quaternion baseRotation;
 int waypoint,carId,orderId;
 string pickupNode,deliveryNode;
 string pickupBuildingId,deliveryBuildingId;
 Vector2 deliveryCoordinate;
 bool byBuilding;
 enum Stage { Idle, Pickup, Delivery }
 Stage stage=Stage.Idle;
 float retryAt,positionAt;
 static readonly CultureInfo C=CultureInfo.InvariantCulture;
 public string State {get{return stage.ToString();}}
 public int OrderId {get{return orderId;}}
 public int CarId {get{return carId;}}
 public bool IsBuildingOrder {get{return orderId>0&&byBuilding;}}
 public string DestinationBuildingId {get{return orderId>0?deliveryBuildingId:null;}}
 public Vector2 DestinationCoordinate {get{return deliveryCoordinate;}}
 public bool Connected {get{return client!=null&&client.Connected;}}
 public void SetGraph(TextAsset asset){graphAsset=asset;}
 void Awake(){
  baseRotation=transform.rotation;
  graph=SimulationGraph.Load(graphAsset);
  Debug.Log("[car] graph loaded nodes="+graph.Nodes.Count+" position="+transform.position);
 }
 void Update(){
  PollNetwork();
  if(stage!=Stage.Idle)Drive(Time.deltaTime);
  if(Connected&&carId>0&&Time.time>=positionAt){positionAt=Time.time+2f;Vector2 p=WorldToMap(transform.position);Send("POSITION,"+carId+","+p.x.ToString("F3",C)+","+p.y.ToString("F3",C));}
 }
 static Vector3 MapToWorld(Vector2 p){return new Vector3(-p.x,0.045f,-p.y);}
 static Vector2 WorldToMap(Vector3 p){return new Vector2(-p.x,-p.z);}
 void PollNetwork(){
  if(client==null){
   if(Time.time<retryAt)return;
   client=new TcpClient();connectTask=client.ConnectAsync("127.0.0.1",10000);retryAt=Time.time+3f;return;
  }
  if(connectTask!=null){
   if(!connectTask.IsCompleted)return;
   if(connectTask.IsFaulted||connectTask.IsCanceled){Disconnect("connect failed");return;}
   connectTask=null;client.NoDelay=true;Send("LOGIN,UNITY");Debug.Log("[car] TCP connected");
  }
  try{
   if(client.Client.Poll(0,SelectMode.SelectRead)&&client.Client.Available==0){Disconnect("server closed");return;}
   NetworkStream stream=client.GetStream();
   while(stream.DataAvailable){int n=stream.Read(bytes,0,bytes.Length);if(n<=0){Disconnect("server closed");return;}
    incoming.Append(Encoding.UTF8.GetString(bytes,0,n));if(incoming.Length>8192){Disconnect("message too long");return;}}
   string text=incoming.ToString();int end;
   while((end=text.IndexOf('\n'))>=0){string line=text.Substring(0,end).TrimEnd('\r');text=text.Substring(end+1);Handle(line);}
   incoming.Clear();incoming.Append(text);
  }catch(Exception e){Disconnect(e.Message);}
 }
 void Handle(string line){
  Debug.Log("[car] received "+line);
  string[] f=line.Split(',');
  if(f.Length==3&&f[0]=="WELCOME"&&f[1]=="UNITY"){carId=int.Parse(f[2],C);return;}
  bool buildingTask=f.Length==11&&f[0]=="TASK_BUILDINGS";
  if(!buildingTask&&(f.Length!=7||f[0]!="TASK"))return;
  float px,py,dx,dy;int assigned,id;
  if(!float.TryParse(f[1],NumberStyles.Float,C,out px)||!float.TryParse(f[2],NumberStyles.Float,C,out py)||
   !float.TryParse(f[3],NumberStyles.Float,C,out dx)||!float.TryParse(f[4],NumberStyles.Float,C,out dy)||
   !int.TryParse(f[5],out assigned)||!int.TryParse(f[6],out id)||assigned!=carId||stage!=Stage.Idle)return;
  string sourceId=buildingTask?f[7]:null;
  string targetId=buildingTask?f[8]:null;
  float pd,dd;
  if(buildingTask){
   Vector2 source,target;
   if(string.IsNullOrEmpty(sourceId)||string.IsNullOrEmpty(targetId)||
      !graph.Nodes.TryGetValue(f[9],out source)||!graph.Nodes.TryGetValue(f[10],out target)||
      Vector2.Distance(source,new Vector2(px,py))>.75f||
      Vector2.Distance(target,new Vector2(dx,dy))>.75f){
    RejectTask(id,sourceId,true,"building node/coordinate mismatch");return;
   }
   pickupNode=f[9];deliveryNode=f[10];
  }else{
   pickupNode=graph.Nearest(new Vector2(px,py),out pd);
   deliveryNode=graph.Nearest(new Vector2(dx,dy),out dd);
   if(pd>6f||dd>6f){RejectTask(id,null,false,"TASK outside simulation road graph");return;}
  }
  float startDistance;string start=graph.Nearest(WorldToMap(transform.position),out startDistance);
  if(startDistance>6f){RejectTask(id,sourceId,buildingTask,"starting position outside graph");return;}
  List<Vector2> planned;
  try{planned=graph.Route(start,pickupNode);graph.Route(pickupNode,deliveryNode);}
  catch(Exception e){RejectTask(id,sourceId,buildingTask,"route failed: "+e.Message);return;}
  orderId=id;byBuilding=buildingTask;pickupBuildingId=sourceId;deliveryBuildingId=targetId;
  deliveryCoordinate=new Vector2(dx,dy);
  stage=Stage.Pickup;SetRoute(planned);
  Debug.Log("[car] order "+id+" "+sourceId+" -> "+targetId+
            " route "+start+" -> "+pickupNode+" -> "+deliveryNode);
 }
 void RejectTask(int id,string sourceId,bool buildingTask,string reason){
  Debug.LogError("[car] "+reason);
  Send(buildingTask?"REPORT_BUILDING,REJECTED,"+carId+","+id+","+sourceId:
                    "REPORT,REJECTED,"+carId+","+id);
 }
 void ReportArrival(string phase,string buildingId){
  Send(byBuilding?"REPORT_BUILDING,"+phase+","+carId+","+orderId+","+buildingId:
                  "REPORT,"+phase+","+carId+","+orderId);
 }
 void SetRoute(List<Vector2> points){route.Clear();route.AddRange(points);waypoint=0;}
 void Drive(float dt){
  while(waypoint<route.Count&&Vector3.Distance(transform.position,MapToWorld(route[waypoint]))<0.18f)waypoint++;
  if(waypoint>=route.Count){
   if(stage==Stage.Pickup){
    ReportArrival("PICKUP",pickupBuildingId);
    Debug.Log("[car] PICKUP order="+orderId+" building="+pickupBuildingId+" pos="+transform.position);
    stage=Stage.Delivery;SetRoute(graph.Route(pickupNode,deliveryNode));
   }else{
    ReportArrival("ARRIVED",deliveryBuildingId);
    Debug.Log("[car] ARRIVED order="+orderId+" building="+deliveryBuildingId+" pos="+transform.position);
    stage=Stage.Idle;orderId=0;byBuilding=false;pickupBuildingId=null;deliveryBuildingId=null;
    deliveryCoordinate=default(Vector2);route.Clear();
   }
   return;
  }
  Vector3 target=MapToWorld(route[waypoint]);Vector3 direction=target-transform.position;direction.y=0;
  if(direction.sqrMagnitude>0.01f){
   // Buildings occupy layer 8. The road and ground do not block the horizontal sensor.
   if(Physics.Raycast(transform.position+Vector3.up*0.45f,direction.normalized,obstacleDistance,1<<8))return;
   float angle=Vector3.SignedAngle(initialForward,direction.normalized,Vector3.up);
   transform.rotation=Quaternion.RotateTowards(transform.rotation,Quaternion.AngleAxis(angle,Vector3.up)*baseRotation,360f*dt);
  }
  transform.position=Vector3.MoveTowards(transform.position,target,speedMetresPerSecond*dt);
 }
 void Send(string line){
  try{if(client==null||connectTask!=null||!client.Connected)return;byte[] data=Encoding.UTF8.GetBytes(line+"\n");client.GetStream().Write(data,0,data.Length);}
  catch(Exception e){Disconnect(e.Message);}
 }
 void Disconnect(string why){
  Debug.LogWarning("[car] disconnected: "+why);if(client!=null)client.Close();client=null;connectTask=null;carId=0;retryAt=Time.time+3f;
  if(stage!=Stage.Idle){stage=Stage.Idle;orderId=0;byBuilding=false;pickupBuildingId=null;deliveryBuildingId=null;deliveryCoordinate=default(Vector2);route.Clear();}
 }
 void OnDestroy(){if(client!=null)client.Close();}
}
