using UnityEngine;
public sealed class DemoHud : MonoBehaviour {
 public CampusCarController car;
 GUIStyle style;
 FollowCarCamera view;
 void OnGUI(){
  if(car==null)return;
  if(view==null&&Camera.main!=null)view=Camera.main.GetComponent<FollowCarCamera>();
  if(style==null){style=new GUIStyle(GUI.skin.box);style.fontSize=18;style.alignment=TextAnchor.UpperLeft;style.normal.textColor=Color.white;}
  GUI.Box(new Rect(16,16,620,145),"Campus Delivery Demo\nServer: "+(car.Connected?"connected":"connecting")+"    Car ID: "+car.CarId+"\nState: "+car.State+"    Order: "+car.OrderId+"\nMap position: "+(-car.transform.position.x).ToString("F1")+", "+(-car.transform.position.z).ToString("F1")+"\nView: "+(view!=null?view.ModeLabel:"Overview")+"    O: overview    F: follow    Wheel: zoom",style);
  if(view!=null&&view.ModeLabel=="Overview"){
   Vector3 point=Camera.main.WorldToScreenPoint(car.transform.position+Vector3.up*1.5f);
   if(point.z>0&&point.x>=0&&point.x<Screen.width&&point.y>=0&&point.y<Screen.height){
    float y=Screen.height-point.y;
    Color old=GUI.color;GUI.color=new Color(1f,.34f,.08f);
    GUI.DrawTexture(new Rect(point.x-7,y-7,14,14),Texture2D.whiteTexture);
    GUI.color=old;
    GUI.Label(new Rect(point.x+10,y-10,45,22),"CAR");
   }
  }
 }
}
