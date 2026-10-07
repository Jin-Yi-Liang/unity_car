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
 enum Stage { Idle, Pickup, Delivery }
 Stage stage=Stage.Idle;
 float retryAt,positionAt;
 static readonly CultureInfo C=CultureInfo.InvariantCulture;
 public string State {get{return stage.ToString();}}
 public int OrderId {get{return orderId;}}
 public int CarId {get{return carId;}}
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
  if(f.Length!=7||f[0]!="TASK")return;
  float px,py,dx,dy;int assigned,id;
  if(!float.TryParse(f[1],NumberStyles.Float,C,out px)||!float.TryParse(f[2],NumberStyles.Float,C,out py)||
   !float.TryParse(f[3],NumberStyles.Float,C,out dx)||!float.TryParse(f[4],NumberStyles.Float,C,out dy)||
   !int.TryParse(f[5],out assigned)||!int.TryParse(f[6],out id)||assigned!=carId||stage!=Stage.Idle)return;
  float pd,dd;pickupNode=graph.Nearest(new Vector2(px,py),out pd);deliveryNode=graph.Nearest(new Vector2(dx,dy),out dd);
  if(pd>6f||dd>6f){Debug.LogError("[car] TASK outside simulation road graph");Send("REPORT,REJECTED,"+carId+","+id);return;}
  float startDistance;string start=graph.Nearest(WorldToMap(transform.position),out startDistance);
  if(startDistance>6f){Debug.LogError("[car] starting position outside graph");Send("REPORT,REJECTED,"+carId+","+id);return;}
  List<Vector2> planned;
  try{planned=graph.Route(start,pickupNode);graph.Route(pickupNode,deliveryNode);}
  catch(Exception e){Debug.LogError("[car] route failed: "+e.Message);Send("REPORT,REJECTED,"+carId+","+id);return;}
  orderId=id;stage=Stage.Pickup;SetRoute(planned);
  Debug.Log("[car] order "+id+" route to pickup "+start+" -> "+pickupNode);
 }
 void SetRoute(List<Vector2> points){route.Clear();route.AddRange(points);waypoint=0;}
 void Drive(float dt){
  while(waypoint<route.Count&&Vector3.Distance(transform.position,MapToWorld(route[waypoint]))<0.18f)waypoint++;
  if(waypoint>=route.Count){
   if(stage==Stage.Pickup){Send("REPORT,PICKUP,"+carId+","+orderId);Debug.Log("[car] PICKUP order="+orderId+" pos="+transform.position);stage=Stage.Delivery;SetRoute(graph.Route(pickupNode,deliveryNode));}
   else {Send("REPORT,ARRIVED,"+carId+","+orderId);Debug.Log("[car] ARRIVED order="+orderId+" pos="+transform.position);stage=Stage.Idle;orderId=0;route.Clear();}
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
  if(stage!=Stage.Idle){stage=Stage.Idle;orderId=0;route.Clear();}
 }
 void OnDestroy(){if(client!=null)client.Close();}
}
