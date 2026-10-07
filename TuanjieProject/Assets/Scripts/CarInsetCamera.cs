using UnityEngine;

[RequireComponent(typeof(Camera))]
public sealed class CarInsetCamera : MonoBehaviour {
 public Transform target;
 public FollowCarCamera overview;
 public Vector3 offset=new Vector3(0,3,-4.5f);

 Camera view;
 void Awake(){view=GetComponent<Camera>();}
 public void PlaceNow(){
  if(target==null)return;
  transform.position=target.position+offset;
  transform.LookAt(target.position+Vector3.up*.6f);
 }
 void LateUpdate(){
  if(view==null)view=GetComponent<Camera>();
  bool show=target!=null&&(overview==null||overview.ModeLabel=="Overview");
  view.enabled=show;
  if(!show)return;
  PlaceNow();
 }
}
