using UnityEditor;
using UnityEngine;

[CustomEditor(typeof(BuildingIdentity))]
public sealed class BuildingIdentityEditor : Editor {
 public override void OnInspectorGUI(){
  var identity=(BuildingIdentity)target;
  var record=identity.Record;
  EditorGUILayout.LabelField("Stable ID (backend key)",record.stableId);
  EditorGUILayout.LabelField("Source mesh",record.meshId);
  EditorGUILayout.LabelField("Original map label",record.mapLabel);
  EditorGUILayout.LabelField("Source traces",string.Join(", ",record.sourceTraceIds));
  EditorGUILayout.LabelField("Visual center (map XY)",record.centerX.ToString("F2")+", "+record.centerY.ToString("F2"));
  EditorGUILayout.LabelField("Navigation status",record.navigationStatus);
  if(record.navigationStatus=="simulation_dock")
   EditorGUILayout.LabelField("Simulation dock node",record.dockNodeId);
  EditorGUI.BeginChangeCheck();
  string name=EditorGUILayout.TextField("Display name",record.displayName);
  if(EditorGUI.EndChangeCheck()){
   if(string.IsNullOrWhiteSpace(name)){Debug.LogWarning("Building name cannot be empty");return;}
   Undo.RecordObject(identity,"Rename building");
   Undo.RecordObject(identity.gameObject,"Rename building hierarchy item");
   identity.SetDisplayName(name);
   EditorUtility.SetDirty(identity);
  }
  EditorGUILayout.HelpBox("Change only the display name. Export the catalog after saving the scene; backend lookup uses the stable ID.",MessageType.Info);
 }
}
