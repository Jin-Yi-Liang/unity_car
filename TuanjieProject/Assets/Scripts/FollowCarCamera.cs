using UnityEngine;

[RequireComponent(typeof(Camera))]
public sealed class FollowCarCamera : MonoBehaviour {
 public Transform target;
 public Vector3 followOffset=new Vector3(0,7,-10);
 Camera view;
 Vector3 overviewCenter,overviewOffset;
 float fittedSize,zoomSize;
 int viewIndex;
 public string ModeLabel {get{return VehicleViewCamera.ViewNames[viewIndex];}}
 public int ViewIndex {get{return viewIndex;}}
 public void SelectView(int index){viewIndex=Mathf.Clamp(index,0,5);Debug.Log("[camera] selected "+(viewIndex+1)+" "+ModeLabel);}
 void Awake(){
  view=GetComponent<Camera>();Renderer ground=null;
  if(target!=null)foreach(Renderer item in target.root.GetComponentsInChildren<Renderer>(true))if(item.name=="Ground"){ground=item;break;}
  ConfigureOverview(ground!=null?ground.bounds:new Bounds(Vector3.zero,new Vector3(920,44,1104)));
 }
 public void ConfigureOverview(Bounds bounds){
  if(view==null)view=GetComponent<Camera>();
  overviewCenter=new Vector3(bounds.center.x,0,bounds.center.z);
  float span=Mathf.Max(bounds.size.x,bounds.size.z);overviewOffset=new Vector3(0,span*.8f,-span*.8f);
  fittedSize=Mathf.Max((bounds.size.z*.7071068f+60)*.5f,bounds.size.x/(2*Mathf.Max(view.aspect,.1f)))*1.12f;
  zoomSize=fittedSize;ApplyOverview();
 }
 void Update(){
  if(Input.GetKeyDown(KeyCode.F))SelectView(1);
  if(Input.GetKeyDown(KeyCode.O))SelectView(0);
  for(int i=0;i<6;i++)if(Input.GetKeyDown((KeyCode)((int)KeyCode.Alpha1+i)))SelectView(i);
  if(viewIndex==0&&Mathf.Abs(Input.mouseScrollDelta.y)>.01f)
   zoomSize=Mathf.Clamp(zoomSize*Mathf.Pow(.86f,Input.mouseScrollDelta.y),fittedSize*.18f,fittedSize*1.5f);
 }
 void LateUpdate(){if(viewIndex==0)ApplyOverview();else VehicleViewCamera.Apply(view,target,viewIndex);}
 void ApplyOverview(){
  view.orthographic=true;view.orthographicSize=zoomSize;view.farClipPlane=3000;
  transform.position=overviewCenter+overviewOffset;transform.LookAt(overviewCenter);
 }
}
