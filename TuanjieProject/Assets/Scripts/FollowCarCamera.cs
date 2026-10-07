using UnityEngine;
public sealed class FollowCarCamera : MonoBehaviour {
 public Transform target;
 public Vector3 offset=new Vector3(0,7,-10);
 void LateUpdate(){if(target==null)return;transform.position=target.position+offset;transform.LookAt(target.position+Vector3.up*1.0f);}
}
