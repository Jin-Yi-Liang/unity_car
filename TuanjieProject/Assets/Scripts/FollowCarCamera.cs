using UnityEngine;

[RequireComponent(typeof(Camera))]
public sealed class FollowCarCamera : MonoBehaviour {
 public Transform target;
 public Vector3 followOffset=new Vector3(0,7,-10);

 Camera view;
 Vector3 overviewCenter;
 Vector3 overviewOffset;
 float fittedSize;
 float zoomSize;
 bool followMode;
 public string ModeLabel { get { return followMode?"Follow":"Overview"; } }

 void Awake(){
  view=GetComponent<Camera>();
  Renderer ground=null;
  if(target!=null){
   foreach(Renderer item in target.root.GetComponentsInChildren<Renderer>(true))
    if(item.name=="Ground"){ground=item;break;}
  }
  ConfigureOverview(ground!=null?ground.bounds:new Bounds(Vector3.zero,new Vector3(920,44,1104)));
 }

 // The campus Ground supplies the map's actual extents in Tuanjie world metres.
 public void ConfigureOverview(Bounds groundBounds){
  if(view==null)view=GetComponent<Camera>();
  overviewCenter=new Vector3(groundBounds.center.x,0,groundBounds.center.z);
  float span=Mathf.Max(groundBounds.size.x,groundBounds.size.z);
  overviewOffset=new Vector3(0,span*.8f,-span*.8f);
  float projectedDepth=groundBounds.size.z*.7071068f+60f; // buildings and framing margin
  float verticalHalf=projectedDepth*.5f;
  float horizontalHalf=groundBounds.size.x/(2f*Mathf.Max(view.aspect,.1f));
  fittedSize=Mathf.Max(verticalHalf,horizontalHalf)*1.12f;
  zoomSize=fittedSize;
  ApplyOverview();
 }

 void Update(){
  if(Input.GetKeyDown(KeyCode.F))followMode=true;
  if(Input.GetKeyDown(KeyCode.O))followMode=false;
  if(!followMode){
   float scroll=Input.mouseScrollDelta.y;
   if(Mathf.Abs(scroll)>.01f)
    zoomSize=Mathf.Clamp(zoomSize*Mathf.Pow(.86f,scroll),fittedSize*.18f,fittedSize*1.5f);
  }
 }

 void LateUpdate(){
  if(followMode&&target!=null){
   view.orthographic=false;
   transform.position=target.position+followOffset;
   transform.LookAt(target.position+Vector3.up);
  }else ApplyOverview();
 }

 void ApplyOverview(){
  view.orthographic=true;
  view.orthographicSize=zoomSize;
  view.farClipPlane=Mathf.Max(view.farClipPlane,3000f);
  transform.position=overviewCenter+overviewOffset;
  transform.LookAt(overviewCenter);
 }
}
