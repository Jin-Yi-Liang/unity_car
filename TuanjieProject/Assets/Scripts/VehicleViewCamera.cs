using UnityEngine;

[RequireComponent(typeof(Camera))]
public sealed class VehicleViewCamera : MonoBehaviour {
 public Transform target;
 [Range(1,5)] public int profile=1;
 public static readonly string[] ViewNames={"Overview","Close","Medium","Far","Top","Orbit"};
 public void ApplyNow(){Apply(GetComponent<Camera>(),target,profile);}
 void LateUpdate(){ApplyNow();}
 public static void Apply(Camera camera,Transform car,int mode){
  if(camera==null||car==null)return;
  camera.nearClipPlane=.05f;camera.farClipPlane=3000;
  camera.orthographic=mode==3||mode==4;
  camera.fieldOfView=mode==1?50:55;
  Vector3 offset;
  switch(mode){
   case 2:offset=new Vector3(0,12,-18);break;
   case 3:offset=new Vector3(0,80,-95);camera.orthographicSize=90;break;
   case 4:offset=new Vector3(0,120,0);camera.orthographicSize=42;break;
   case 5:float angle=Time.time*.18f;offset=new Vector3(Mathf.Sin(angle)*16,9,Mathf.Cos(angle)*16);break;
   default:offset=new Vector3(0,3,-4.5f);break;
  }
  camera.transform.position=car.position+offset;
  if(mode==4)camera.transform.rotation=Quaternion.Euler(90,0,0);
  else camera.transform.LookAt(car.position+Vector3.up*.6f);
 }
}
