using System.Collections.Generic;
using UnityEngine;

public sealed class FleetCoordinator : MonoBehaviour {
 public CampusCarController template;
 [Range(1,6)] public int vehicleCount=3;
 public readonly List<CampusCarController> Cars=new List<CampusCarController>();
 int selectedIndex;
 void Awake(){Application.runInBackground=true;}
 public CampusCarController SelectedCar {get{return Cars.Count==0?template:Cars[selectedIndex%Cars.Count];}}
 void Start(){
  if(template==null){Debug.LogError("[fleet] car template missing");return;}
  Cars.Add(template);
  var graph=SimulationGraph.Load(Resources.Load<TextAsset>("simulation_graph"));
  string[] spawns={"SIMNODE_0008","SIMNODE_0007","SIMNODE_0009","SIMNODE_0010","SIMNODE_0006","SIMNODE_0011"};
  for(int i=1;i<vehicleCount;i++){
   var clone=Instantiate(template.gameObject,template.transform.parent);
   clone.name="DeliveryRobot_"+(i+1);
   Vector2 point=graph.Nodes[spawns[i]];
   clone.transform.position=new Vector3(-point.x,.045f,-point.y);
   Cars.Add(clone.GetComponent<CampusCarController>());
  }
  Debug.Log("[fleet] spawned "+Cars.Count+" independently connected cars");
  if(!Application.isEditor)
   for(int i=1;i<Mathf.Min(Display.displays.Length,6);i++)Display.displays[i].Activate();
  SelectCar(0);
 }
 public void SelectCar(int index){
  if(Cars.Count==0)return;
  selectedIndex=(index+Cars.Count)%Cars.Count;
  var selected=SelectedCar;
  foreach(FollowCarCamera view in FindObjectsOfType<FollowCarCamera>())view.target=selected.transform;
  foreach(CarInsetCamera view in FindObjectsOfType<CarInsetCamera>())view.target=selected.transform;
  foreach(VehicleViewCamera view in FindObjectsOfType<VehicleViewCamera>())view.target=selected.transform;
  foreach(DemoHud hud in FindObjectsOfType<DemoHud>())hud.car=selected;
  Debug.Log("[fleet] selected vehicle index="+(selectedIndex+1));
 }
 void Update(){if(Input.GetKeyDown(KeyCode.Tab))SelectCar(selectedIndex+1);}
}
