using System.Collections.Generic;
using UnityEngine;

public sealed class DemoHud : MonoBehaviour {
 public CampusCarController car;
 GUIStyle statusStyle;
 GUIStyle labelStyle;
 FollowCarCamera view;
 readonly Dictionary<string,string> buildingNames=new Dictionary<string,string>();

 void Awake(){
  foreach(BuildingIdentity building in FindObjectsOfType<BuildingIdentity>())
   if(!string.IsNullOrEmpty(building.StableId))buildingNames[building.StableId]=building.DisplayName;
 }

 string DestinationText(){
  if(car.OrderId==0)return "None";
  if(car.IsBuildingOrder){
   string id=car.DestinationBuildingId;
   string name;
   return buildingNames.TryGetValue(id,out name)?id+" - "+name:id;
  }
  Vector2 point=car.DestinationCoordinate;
  return "("+point.x.ToString("F1")+", "+point.y.ToString("F1")+")";
 }

 void OnGUI(){
  if(car==null)return;
  Camera main=Camera.main;
  if(view==null&&main!=null)view=main.GetComponent<FollowCarCamera>();
  float scale=Mathf.Max(1f,Screen.height/720f);
  if(statusStyle==null){statusStyle=new GUIStyle(GUI.skin.box);statusStyle.alignment=TextAnchor.UpperLeft;statusStyle.normal.textColor=Color.white;}
  if(labelStyle==null){labelStyle=new GUIStyle(GUI.skin.box);labelStyle.alignment=TextAnchor.MiddleCenter;labelStyle.normal.textColor=Color.white;labelStyle.fontStyle=FontStyle.Bold;}
  statusStyle.fontSize=Mathf.RoundToInt(18*scale);
  labelStyle.fontSize=Mathf.RoundToInt(16*scale);
  GUI.Box(new Rect(16*scale,16*scale,620*scale,173*scale),
   "Campus Delivery Demo\nServer: "+(car.Connected?"connected":"connecting")+"    Car ID: "+car.CarId+
   "\nState: "+car.State+"    Order: "+car.OrderId+
   "\nDestination: "+DestinationText()+
   "\nMap position: "+(-car.transform.position.x).ToString("F1")+", "+(-car.transform.position.z).ToString("F1")+
   "\nView: "+(view!=null?view.ModeLabel:"Overview")+"    O: overview    F: follow    Wheel: zoom",statusStyle);
  if(main==null||view==null||view.ModeLabel!="Overview")return;

  // Keep the car locatable even when 1.2 metres occupy only a few pixels on the campus map.
  Vector3 point=main.WorldToScreenPoint(car.transform.position+Vector3.up*1.5f);
  if(point.z>0&&point.x>=0&&point.x<Screen.width&&point.y>=0&&point.y<Screen.height){
   float y=Screen.height-point.y;
   float size=30*scale;
   Color old=GUI.color;
   GUI.color=Color.black;
   GUI.DrawTexture(new Rect(point.x-size*.5f-4*scale,y-size*.5f-4*scale,size+8*scale,size+8*scale),Texture2D.whiteTexture);
   GUI.color=new Color(1f,.34f,.08f);
   GUI.DrawTexture(new Rect(point.x-size*.5f,y-size*.5f,size,size),Texture2D.whiteTexture);
   GUI.color=old;
   GUI.Box(new Rect(point.x+size*.5f+6*scale,y-size*.5f,64*scale,30*scale),"CAR",labelStyle);
  }

  // The second camera renders the actual car model in the upper right.
  Rect inset=new Rect(Screen.width*.72f,Screen.height*.02f,Screen.width*.27f,Screen.height*.30f);
  Color previous=GUI.color;
  GUI.color=Color.black;
  float border=3*scale;
  GUI.DrawTexture(new Rect(inset.x-border,inset.y-border,inset.width+2*border,border),Texture2D.whiteTexture);
  GUI.DrawTexture(new Rect(inset.x-border,inset.y+inset.height,inset.width+2*border,border),Texture2D.whiteTexture);
  GUI.DrawTexture(new Rect(inset.x-border,inset.y,border,inset.height),Texture2D.whiteTexture);
  GUI.DrawTexture(new Rect(inset.x+inset.width,inset.y,border,inset.height),Texture2D.whiteTexture);
  GUI.color=previous;
  GUI.Box(new Rect(inset.x+6*scale,inset.y+6*scale,120*scale,28*scale),"CAR VIEW",labelStyle);
 }
}
