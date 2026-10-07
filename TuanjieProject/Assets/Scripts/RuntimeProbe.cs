using UnityEngine;
public sealed class RuntimeProbe : MonoBehaviour {
 public CampusCarController car;
 float next;
 void Update(){
  if(Time.time<next)return;next=Time.time+5f;
  if(car!=null)Debug.Log("[runtime] car="+car.transform.position+" state="+car.State+" order="+car.OrderId+" connected="+car.Connected);
 }
}
