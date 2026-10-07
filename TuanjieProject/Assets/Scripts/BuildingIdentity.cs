using System;
using UnityEngine;

[Serializable]
public sealed class BuildingRecord {
 public string stableId;
 public string meshId;
 public string displayName;
 public string mapLabel;
 public string[] sourceTraceIds;
 public float centerX;
 public float centerY;
 public string navigationStatus;
 public string dockNodeId;
 public float dockX;
 public float dockY;
 public BuildingRecord Copy(){
  return new BuildingRecord{
   stableId=stableId,meshId=meshId,displayName=displayName,mapLabel=mapLabel,
   sourceTraceIds=sourceTraceIds==null?new string[0]:(string[])sourceTraceIds.Clone(),
   centerX=centerX,centerY=centerY,navigationStatus=navigationStatus,dockNodeId=dockNodeId,
   dockX=dockX,dockY=dockY
  };
 }
}

[Serializable]
public sealed class BuildingCatalogData {
 public int schemaVersion=1;
 public BuildingRecord[] buildings;
}

public sealed class BuildingIdentity : MonoBehaviour {
 [SerializeField, HideInInspector] BuildingRecord record=new BuildingRecord();
 public BuildingRecord Record { get { return record.Copy(); } }
 public string StableId { get { return record.stableId; } }
 public string DisplayName { get { return record.displayName; } }
 public void SetRecord(BuildingRecord value,string nameOverride=null){
  record=value.Copy();
  if(!string.IsNullOrWhiteSpace(nameOverride))record.displayName=nameOverride.Trim();
  SyncHierarchyName();
 }
 public void SetDisplayName(string value){
  if(string.IsNullOrWhiteSpace(value))throw new ArgumentException("Building name cannot be empty");
  record.displayName=value.Trim();SyncHierarchyName();
 }
 void SyncHierarchyName(){
  if(!string.IsNullOrEmpty(record.stableId))gameObject.name=record.stableId+" · "+record.displayName;
 }
}
