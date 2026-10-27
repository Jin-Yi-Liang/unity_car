using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
public static class SceneBuilder {
 const string ScenePath="Assets/Scenes/CampusDelivery.unity";
 const string RegistryPath="Assets/Resources/building_registry.json";
 static BuildingCatalogData LoadRegistry(){
  var asset=AssetDatabase.LoadAssetAtPath<TextAsset>(RegistryPath);
  if(asset==null)throw new Exception("building registry missing: "+RegistryPath);
  var catalog=JsonUtility.FromJson<BuildingCatalogData>(asset.text);
  if(catalog==null||catalog.buildings==null||catalog.buildings.Length==0)
   throw new Exception("building registry is empty or invalid");
  return catalog;
 }
 static Dictionary<string,string> ExistingNames(){
  var names=new Dictionary<string,string>();
  if(!File.Exists(ScenePath))return names;
  Scene old=SceneManager.GetSceneByPath(ScenePath);
  bool temporary=!old.IsValid()||!old.isLoaded;
  if(temporary)old=EditorSceneManager.OpenScene(ScenePath,OpenSceneMode.Additive);
  foreach(GameObject root in old.GetRootGameObjects())
   foreach(BuildingIdentity building in root.GetComponentsInChildren<BuildingIdentity>(true))
    if(!string.IsNullOrEmpty(building.StableId))names[building.StableId]=building.DisplayName;
  if(temporary)EditorSceneManager.CloseScene(old,true);
  return names;
 }
 [MenuItem("Campus/Export Building Catalog for Backend")]
 public static void ExportBuildingCatalog(){
  var source=LoadRegistry();
  var scene=EditorSceneManager.GetActiveScene();
  var found=new Dictionary<string,BuildingRecord>();
  foreach(GameObject root in scene.GetRootGameObjects())
   foreach(BuildingIdentity identity in root.GetComponentsInChildren<BuildingIdentity>(true)){
    BuildingRecord record=identity.Record;
    if(string.IsNullOrWhiteSpace(record.displayName)||found.ContainsKey(record.stableId))
     throw new Exception("invalid/duplicate building ID: "+record.stableId);
    found.Add(record.stableId,record);
   }
  if(found.Count!=source.buildings.Length)throw new Exception("scene building count differs from registry");
  var output=new BuildingCatalogData{schemaVersion=1,buildings=new BuildingRecord[source.buildings.Length]};
  for(int i=0;i<source.buildings.Length;i++){
   var expected=source.buildings[i];
   if(!found.TryGetValue(expected.stableId,out BuildingRecord record)||record.meshId!=expected.meshId)
    throw new Exception("building identity mismatch: "+expected.stableId);
   output.buildings[i]=record;
  }
  string path=Path.GetFullPath(Path.Combine(Application.dataPath,"../../data/buildings-unity.json"));
  Directory.CreateDirectory(Path.GetDirectoryName(path));
  File.WriteAllText(path,JsonUtility.ToJson(output,true)+"\n");
  Debug.Log("[builder] exported "+output.buildings.Length+" buildings to "+path);
 }
 public static void ExportSavedSceneCatalog(){
  EditorSceneManager.OpenScene(ScenePath,OpenSceneMode.Single);
  ExportBuildingCatalog();
 }
 [MenuItem("Campus/Upgrade All Building Docks")]
 public static void UpgradeAllBuildingDocks(){
  AssetDatabase.Refresh();
  var scene=EditorSceneManager.OpenScene(ScenePath,OpenSceneMode.Single);
  var registry=LoadRegistry();var records=new Dictionary<string,BuildingRecord>();
  foreach(var item in registry.buildings)records.Add(item.stableId,item);
  int updated=0;
  foreach(var root in scene.GetRootGameObjects())
   foreach(var identity in root.GetComponentsInChildren<BuildingIdentity>(true)){
    var before=identity.Record;
    if(!records.TryGetValue(before.stableId,out BuildingRecord record)||record.meshId!=before.meshId)
     throw new Exception("unregistered building "+before.stableId);
    identity.SetRecord(record,before.displayName);EditorUtility.SetDirty(identity);updated++;
   }
  if(updated!=records.Count)throw new Exception("building count mismatch during dock upgrade");
  var old=GameObject.Find("Delivery Docks");if(old!=null)UnityEngine.Object.DestroyImmediate(old);
  var holder=new GameObject("Delivery Docks");
  var material=new Material(Shader.Find("Standard"));material.color=new Color(.025f,.65f,.65f);
  const string materialPath="Assets/Materials/DeliveryDock.mat";
  Directory.CreateDirectory("Assets/Materials");
  var saved=AssetDatabase.LoadAssetAtPath<Material>(materialPath);
  if(saved==null){AssetDatabase.CreateAsset(material,materialPath);saved=material;}
  else UnityEngine.Object.DestroyImmediate(material);
  foreach(var record in registry.buildings){
   if(record.navigationStatus!="simulation_dock")throw new Exception("dock missing "+record.stableId);
   var marker=GameObject.CreatePrimitive(PrimitiveType.Cylinder);
   marker.name=record.stableId+" - "+record.dockNodeId;marker.transform.SetParent(holder.transform,false);
   marker.transform.position=new Vector3(-record.dockX,.07f,-record.dockY);
   marker.transform.localScale=new Vector3(2.4f,.02f,2.4f);
   UnityEngine.Object.DestroyImmediate(marker.GetComponent<Collider>());
   marker.GetComponent<Renderer>().sharedMaterial=saved;
  }
  EditorSceneManager.SaveScene(scene,ScenePath);AssetDatabase.SaveAssets();
  ExportBuildingCatalog();
  Debug.Log("[docks] upgraded "+updated+" buildings; preserved scene display names");
 }
 public static void ValidateAllBuildingRoutes(){
  var scene=EditorSceneManager.OpenScene(ScenePath,OpenSceneMode.Single);
  var registry=LoadRegistry();var graph=SimulationGraph.Load(Resources.Load<TextAsset>("simulation_graph"));
  var unique=new HashSet<string>();int pairs=0,segments=0;
  foreach(var item in registry.buildings){
   if(item.navigationStatus!="simulation_dock"||!unique.Add(item.dockNodeId)||
      !graph.Nodes.TryGetValue(item.dockNodeId,out Vector2 point)||
      Vector2.Distance(point,new Vector2(item.dockX,item.dockY))>.01f)
    throw new Exception("invalid or duplicate dock "+item.stableId);
   foreach(var goal in registry.buildings){
    if(item.stableId==goal.stableId)continue;
    var route=graph.Route(item.dockNodeId,goal.dockNodeId);
    if(route.Count<2||Vector2.Distance(route[route.Count-1],new Vector2(goal.dockX,goal.dockY))>.01f)
     throw new Exception("invalid route "+item.stableId+" -> "+goal.stableId);
    pairs++;
   }
  }
  Physics.SyncTransforms();var checkedEdges=new HashSet<SimulationGraph.Edge>();
  foreach(var list in graph.Adjacent.Values)foreach(var edge in list){
   if(!checkedEdges.Add(edge))continue;
   for(int i=1;i<edge.Points.Count;i++){
    var a=new Vector3(-edge.Points[i-1].x,.495f,-edge.Points[i-1].y);
    var b=new Vector3(-edge.Points[i].x,.495f,-edge.Points[i].y);var delta=b-a;
    if(Physics.CheckSphere(a,.75f,1<<8)||Physics.SphereCast(a,.75f,delta.normalized,out RaycastHit hit,delta.magnitude,1<<8)||
       Physics.Raycast(a,delta.normalized,delta.magnitude+2f,1<<8))
     throw new Exception("building collider blocks road "+edge.From+" -> "+edge.To);
    segments++;
   }
  }
  Debug.Log("[docks] PASS buildings="+unique.Count+" orderedPairs="+pairs+" collisionCheckedSegments="+segments);
 }
 public static void UpgradeAllDocksAndBuildPlayer(){
  UpgradeAllBuildingDocks();ValidateAllBuildingRoutes();BuildPlayer();
 }
 static void EnsureCarDetailCamera(FollowCarCamera main){
  if(main.target==null)throw new Exception("car camera target missing");
  var detail=GameObject.Find("Car Detail Camera");
  if(detail==null)detail=new GameObject("Car Detail Camera");
  var camera=detail.GetComponent<Camera>();
  if(camera==null)camera=detail.AddComponent<Camera>();
  detail.tag="Untagged";
  camera.clearFlags=CameraClearFlags.SolidColor;
  camera.backgroundColor=new Color(.18f,.22f,.25f);
  camera.rect=new Rect(.72f,.68f,.27f,.30f);
  camera.depth=1;
  camera.fieldOfView=50;
  camera.nearClipPlane=.05f;
  camera.farClipPlane=250;
  var inset=detail.GetComponent<CarInsetCamera>();
  if(inset==null)inset=detail.AddComponent<CarInsetCamera>();
  inset.target=main.target;
  inset.overview=main;
  inset.PlaceNow();
 }
 static void EnsureFleetAndViews(FollowCarCamera main){
  var holder=GameObject.Find("Fleet Coordinator");
  if(holder==null)holder=new GameObject("Fleet Coordinator");
  var fleet=holder.GetComponent<FleetCoordinator>();
  if(fleet==null)fleet=holder.AddComponent<FleetCoordinator>();
  fleet.template=main.target.GetComponent<CampusCarController>();fleet.vehicleCount=3;
  for(int profile=1;profile<=5;profile++){
   string name="Display "+(profile+1)+" - "+VehicleViewCamera.ViewNames[profile];
   var item=GameObject.Find(name);if(item==null)item=new GameObject(name);
   var camera=item.GetComponent<Camera>();if(camera==null)camera=item.AddComponent<Camera>();
   item.tag="Untagged";camera.targetDisplay=profile;camera.depth=0;camera.rect=new Rect(0,0,1,1);
   camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(.18f,.22f,.25f);
   var view=item.GetComponent<VehicleViewCamera>();if(view==null)view=item.AddComponent<VehicleViewCamera>();
   view.target=main.target;view.profile=profile;view.ApplyNow();
   Debug.Log("[builder] "+name+" targetDisplay="+camera.targetDisplay);
  }
 }
 [MenuItem("Campus/Upgrade Fleet and Displays")]
 public static void UpgradeFleetAndDisplays(){
  var scene=EditorSceneManager.OpenScene(ScenePath,OpenSceneMode.Single);
  var main=Camera.main.GetComponent<FollowCarCamera>();
  EnsureFleetAndViews(main);EditorSceneManager.MarkSceneDirty(scene);EditorSceneManager.SaveScene(scene);
  Debug.Log("[builder] fleet=3 displays=6, preserved existing scene and building names");
 }
 public static void RenderDisplayPreviews(){
  EditorSceneManager.OpenScene(ScenePath,OpenSceneMode.Single);
  string folder=Path.GetFullPath(Path.Combine(Application.dataPath,"../../build/display-previews"));Directory.CreateDirectory(folder);
  foreach(Camera camera in UnityEngine.Object.FindObjectsOfType<Camera>()){
   if(camera.name=="Car Detail Camera")continue;
   var target=new RenderTexture(1280,720,24);var previous=RenderTexture.active;var old=camera.targetTexture;
   try{
    camera.targetTexture=target;camera.Render();RenderTexture.active=target;
    var image=new Texture2D(1280,720,TextureFormat.RGB24,false);image.ReadPixels(new Rect(0,0,1280,720),0,0);image.Apply();
    File.WriteAllBytes(Path.Combine(folder,"display-"+(camera.targetDisplay+1)+".png"),image.EncodeToPNG());UnityEngine.Object.DestroyImmediate(image);
   }finally{camera.targetTexture=old;RenderTexture.active=previous;target.Release();UnityEngine.Object.DestroyImmediate(target);}
  }
  Debug.Log("[builder] display previews="+folder);
 }
 public static void ValidateFleetAndDisplays(){
  EditorSceneManager.OpenScene(ScenePath,OpenSceneMode.Single);
  var fleet=UnityEngine.Object.FindObjectOfType<FleetCoordinator>();
  if(fleet==null||fleet.vehicleCount!=3||fleet.template==null)throw new Exception("fleet configuration invalid");
  var used=new HashSet<int>();
  foreach(var view in UnityEngine.Object.FindObjectsOfType<VehicleViewCamera>()){
   int display=view.GetComponent<Camera>().targetDisplay;
   if(display!=view.profile||display<1||display>5||!used.Add(display)||view.target==null)
    throw new Exception("display assignment invalid: "+view.name);
  }
  if(used.Count!=5||Camera.main.targetDisplay!=0)throw new Exception("six display cameras required");
  if(UnityEngine.Object.FindObjectsOfType<BuildingIdentity>().Length!=69)throw new Exception("building annotations lost");
  Debug.Log("[validation] PASS fleet=3 displays=1,2,3,4,5,6 buildings=69");
 }
 [MenuItem("Campus/Set Main Camera Overview")]
 public static void SetMainCameraOverview(){
  var scene=EditorSceneManager.GetActiveScene();
  if(scene.path!=ScenePath)scene=EditorSceneManager.OpenScene(ScenePath,OpenSceneMode.Single);
  Camera camera=Camera.main;
  if(camera==null)throw new Exception("Main Camera missing");
  var follow=camera.GetComponent<FollowCarCamera>();
  var ground=GameObject.Find("Ground");
  if(follow==null||ground==null||ground.GetComponent<Renderer>()==null)
   throw new Exception("camera controller or Ground renderer missing");
  follow.ConfigureOverview(ground.GetComponent<Renderer>().bounds);
  EnsureCarDetailCamera(follow);
  EditorSceneManager.MarkSceneDirty(scene);
  EditorSceneManager.SaveScene(scene);
  Debug.Log("[builder] overview camera size="+camera.orthographicSize+" position="+camera.transform.position);
 }
 public static void RenderOverviewPreview(){
  EditorSceneManager.OpenScene(ScenePath,OpenSceneMode.Single);
  Camera camera=Camera.main;
  if(camera==null)throw new Exception("Main Camera missing");
  var target=new RenderTexture(1280,720,24);
  var oldTarget=camera.targetTexture;
  var oldActive=RenderTexture.active;
  try{
   camera.targetTexture=target;
   camera.Render();
   RenderTexture.active=target;
   var image=new Texture2D(1280,720,TextureFormat.RGB24,false);
   image.ReadPixels(new Rect(0,0,1280,720),0,0);
   image.Apply();
   string path=Path.GetFullPath(Path.Combine(Application.dataPath,"../../build/camera-overview-preview.png"));
   Directory.CreateDirectory(Path.GetDirectoryName(path));
   File.WriteAllBytes(path,image.EncodeToPNG());
   UnityEngine.Object.DestroyImmediate(image);
   Debug.Log("[builder] overview preview="+path);
  }finally{
   camera.targetTexture=oldTarget;
   RenderTexture.active=oldActive;
   target.Release();
   UnityEngine.Object.DestroyImmediate(target);
  }
 }
 public static void OpenForReview(){
  var scene=EditorSceneManager.OpenScene(ScenePath,OpenSceneMode.Single);
  foreach(GameObject root in scene.GetRootGameObjects()){
   BuildingIdentity building=root.GetComponentInChildren<BuildingIdentity>(true);
   if(building==null)continue;
   Selection.activeGameObject=building.gameObject;
   EditorApplication.delayCall+=()=>{
    if(SceneView.lastActiveSceneView!=null)SceneView.lastActiveSceneView.FrameSelected();
   };
   break;
  }
  Debug.Log("[builder] opened for review: "+ScenePath);
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
  var previousNames=ExistingNames();
  var registry=LoadRegistry();
  var buildingByMesh=new Dictionary<string,BuildingRecord>();
  foreach(BuildingRecord record in registry.buildings){
   if(buildingByMesh.ContainsKey(record.meshId))throw new Exception("duplicate mesh ID: "+record.meshId);
   buildingByMesh.Add(record.meshId,record);
  }
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
   else if(t.name.StartsWith("BLDG_")){
    if(!buildingByMesh.TryGetValue(t.name,out BuildingRecord record))throw new Exception("unregistered building mesh: "+t.name);
    t.gameObject.layer=8;t.gameObject.AddComponent<MeshCollider>();
    previousNames.TryGetValue(record.stableId,out string editedName);
    t.gameObject.AddComponent<BuildingIdentity>().SetRecord(record,editedName);
    buildings++;
   }
  }
  if(buildings!=registry.buildings.Length)throw new Exception("building count differs from registry");
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
  var ground=FindDeep(campus.transform,"Ground");
  if(ground==null||ground.GetComponent<Renderer>()==null)throw new Exception("Ground renderer missing");
  follow.ConfigureOverview(ground.GetComponent<Renderer>().bounds);
  EnsureCarDetailCamera(follow);
  var light=new GameObject("Sun").AddComponent<Light>();light.type=LightType.Directional;light.intensity=1.1f;light.transform.rotation=Quaternion.Euler(48,-30,0);
  RenderSettings.ambientLight=new Color(0.65f,0.7f,0.75f);
  var probe=new GameObject("Runtime Probe").AddComponent<RuntimeProbe>();probe.car=controller;
  var hud=new GameObject("Status HUD").AddComponent<DemoHud>();hud.car=controller;
  EnsureFleetAndViews(follow);
  Directory.CreateDirectory("Assets/Scenes");
  EditorSceneManager.SaveScene(scene,ScenePath);
  EditorBuildSettings.scenes=new[]{new EditorBuildSettingsScene(ScenePath,true)};
  ExportBuildingCatalog();
  Debug.Log("[builder] scene="+ScenePath+" roads="+roads+" buildings="+buildings+" car="+car.position+" graph="+(controller!=null));
 }
 public static void BuildPlayer(){
  AssetDatabase.Refresh();
  if(File.Exists(ScenePath))EditorSceneManager.OpenScene(ScenePath,OpenSceneMode.Single);
  else BuildScene();
  string output=Path.GetFullPath(Path.Combine(Application.dataPath,"../../build/tuanjie-player/DeliveryDemo.x86_64"));
  Directory.CreateDirectory(Path.GetDirectoryName(output));
  var report=BuildPipeline.BuildPlayer(new[]{"Assets/Scenes/CampusDelivery.unity"},output,BuildTarget.StandaloneLinux64,BuildOptions.None);
  Debug.Log("[builder] player result="+report.summary.result+" output="+output+" errors="+report.summary.totalErrors);
  if(report.summary.result!=BuildResult.Succeeded)throw new Exception("Player build failed");
 }
}
