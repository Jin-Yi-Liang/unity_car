using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
public static class SceneBuilder {
 public static void OpenForReview(){
  string path="Assets/Scenes/CampusDelivery.unity";
  var scene=EditorSceneManager.OpenScene(path,OpenSceneMode.Single);
  foreach(GameObject root in scene.GetRootGameObjects()){
   Transform car=FindDeep(root.transform,"DeliveryRobot_ROOT");
   if(car==null)continue;
   Selection.activeTransform=car;
   EditorApplication.delayCall+=()=>{
    if(SceneView.lastActiveSceneView!=null)SceneView.lastActiveSceneView.FrameSelected();
   };
   break;
  }
  Debug.Log("[builder] opened for review: "+path);
 }
 static Transform FindDeep(Transform root,string name){foreach(Transform t in root.GetComponentsInChildren<Transform>(true))if(t.name==name)return t;return null;}
 static Bounds LocalMeshBounds(Transform root){
  Bounds result=new Bounds();bool found=false;
  foreach(MeshFilter filter in root.GetComponentsInChildren<MeshFilter>(true)){
   if(filter.sharedMesh==null)continue;
   Bounds b=filter.sharedMesh.bounds;
   foreach(float x in new[]{b.min.x,b.max.x})foreach(float y in new[]{b.min.y,b.max.y})foreach(float z in new[]{b.min.z,b.max.z}){
    Vector3 p=root.InverseTransformPoint(filter.transform.TransformPoint(new Vector3(x,y,z)));
    if(!found){result=new Bounds(p,Vector3.zero);found=true;}else result.Encapsulate(p);
   }
  }
  if(!found)throw new Exception("robot has no meshes");
  return result;
 }
 public static void Probe(){
  var asset=AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Models/campus.fbx");
  Debug.Log("[probe] campus="+asset);
  if(asset==null)return;
  Transform robot=FindDeep(asset.transform,"DeliveryRobot_ROOT");
  Debug.Log("[probe] robot="+robot+" position="+robot.position+" rotation="+robot.rotation.eulerAngles);
  var standalone=AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Models/delivery_robot.fbx");
  Debug.Log("[probe] standalone="+standalone);
  if(standalone!=null)Debug.Log("[probe] standalone badge="+FindDeep(standalone.transform,"ROBOT_MealBadge_Left"));
 }
 public static void BuildScene(){
  AssetDatabase.Refresh();
  var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
  var prefab=AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Models/campus.fbx");
  if(prefab==null)throw new Exception("campus.fbx import failed");
  var standalone=AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Models/delivery_robot.fbx");
  if(standalone==null||FindDeep(standalone.transform,"WheelPivot_FL")==null||
     FindDeep(standalone.transform,"ROBOT_MealBadge_Left")==null)
   throw new Exception("standalone delivery_robot.fbx import failed");
  var campus=(GameObject)PrefabUtility.InstantiatePrefab(prefab);
  campus.name="Campus";
  int roads=0,buildings=0;
  foreach(Transform t in campus.GetComponentsInChildren<Transform>(true)){
   var filter=t.GetComponent<MeshFilter>();if(filter==null||filter.sharedMesh==null)continue;
   if(t.name.StartsWith("ROAD_")||t.name.StartsWith("BRIDGE_")){t.gameObject.AddComponent<MeshCollider>();roads++;}
   else if(t.name.StartsWith("BLDG_")){t.gameObject.layer=8;t.gameObject.AddComponent<MeshCollider>();buildings++;}
  }
  Transform car=FindDeep(campus.transform,"DeliveryRobot_ROOT");
  if(car==null)throw new Exception("DeliveryRobot_ROOT missing in campus.fbx");
  if(FindDeep(car,"ROBOT_MealBadge_Left")==null||FindDeep(car,"ROBOT_MealBadge_Right")==null)
   throw new Exception("updated meal delivery model missing in campus.fbx");
  var body=car.gameObject.AddComponent<Rigidbody>();body.isKinematic=true;body.useGravity=false;
  var controller=car.gameObject.AddComponent<CampusCarController>();
  controller.SetGraph(AssetDatabase.LoadAssetAtPath<TextAsset>("Assets/Resources/simulation_graph.txt"));
  Bounds carBounds=LocalMeshBounds(car);
  var collider=car.gameObject.AddComponent<BoxCollider>();collider.center=carBounds.center;collider.size=carBounds.size;
  Debug.Log("[builder] car local bounds="+carBounds+" collider="+collider.size);
  var camera=new GameObject("Main Camera");camera.tag="MainCamera";
  var cam=camera.AddComponent<Camera>();cam.fieldOfView=55;cam.farClipPlane=2500;cam.nearClipPlane=0.05f;
  var follow=camera.AddComponent<FollowCarCamera>();follow.target=car;
  camera.transform.position=car.position+follow.offset;camera.transform.LookAt(car.position);
  var light=new GameObject("Sun").AddComponent<Light>();light.type=LightType.Directional;light.intensity=1.1f;light.transform.rotation=Quaternion.Euler(48,-30,0);
  RenderSettings.ambientLight=new Color(0.65f,0.7f,0.75f);
  var probe=new GameObject("Runtime Probe").AddComponent<RuntimeProbe>();probe.car=controller;
  var hud=new GameObject("Status HUD").AddComponent<DemoHud>();hud.car=controller;
  Directory.CreateDirectory("Assets/Scenes");
  string path="Assets/Scenes/CampusDelivery.unity";
  EditorSceneManager.SaveScene(scene,path);
  EditorBuildSettings.scenes=new[]{new EditorBuildSettingsScene(path,true)};
  Debug.Log("[builder] scene="+path+" roads="+roads+" buildings="+buildings+" car="+car.position+" graph="+(controller!=null));
 }
 public static void BuildPlayer(){
  BuildScene();
  string output=Path.GetFullPath(Path.Combine(Application.dataPath,"../../build/tuanjie-player/DeliveryDemo.x86_64"));
  Directory.CreateDirectory(Path.GetDirectoryName(output));
  var report=BuildPipeline.BuildPlayer(new[]{"Assets/Scenes/CampusDelivery.unity"},output,BuildTarget.StandaloneLinux64,BuildOptions.None);
  Debug.Log("[builder] player result="+report.summary.result+" output="+output+" errors="+report.summary.totalErrors);
  if(report.summary.result!=BuildResult.Succeeded)throw new Exception("Player build failed");
 }
}
