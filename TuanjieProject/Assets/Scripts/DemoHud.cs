using UnityEngine;
public sealed class DemoHud : MonoBehaviour {
 public CampusCarController car;
 GUIStyle style;
 void OnGUI(){
  if(car==null)return;
  if(style==null){style=new GUIStyle(GUI.skin.box);style.fontSize=18;style.alignment=TextAnchor.UpperLeft;style.normal.textColor=Color.white;}
  GUI.Box(new Rect(16,16,560,118),"Campus Delivery Demo\nServer: "+(car.Connected?"connected":"connecting")+"    Car ID: "+car.CarId+"\nState: "+car.State+"    Order: "+car.OrderId+"\nMap position: "+(-car.transform.position.x).ToString("F1")+", "+(-car.transform.position.z).ToString("F1"),style);
 }
}
