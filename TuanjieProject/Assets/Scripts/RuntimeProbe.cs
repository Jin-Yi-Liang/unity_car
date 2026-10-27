using System;
using System.Collections;
using System.IO;
using UnityEngine;

public sealed class RuntimeProbe : MonoBehaviour {
 public CampusCarController car;
 float next;
 void Awake(){
  string speed=Argument("-qa-timescale");float value;
  if(float.TryParse(speed,out value)&&value>=1&&value<=8){
   Time.timeScale=value;
   // Keep the requested QA rate when background rendering limits frame rate.
   Time.maximumDeltaTime=Mathf.Max(Time.maximumDeltaTime,2f*value);
   Time.fixedDeltaTime=.02f*value;
   Debug.Log("[qa] timescale="+value+" maxDelta="+Time.maximumDeltaTime);
  }
 }
 IEnumerator Start(){
  string capture=Argument("-capture-views");
  if(string.IsNullOrEmpty(capture))yield break;
  Directory.CreateDirectory(capture);
  yield return new WaitForSecondsRealtime(8);
  var main=Camera.main.GetComponent<FollowCarCamera>();
  for(int i=0;i<6;i++){
   main.SelectView(i);
   yield return new WaitForSecondsRealtime(.5f);
   yield return new WaitForEndOfFrame();
   ScreenCapture.CaptureScreenshot(Path.Combine(capture,"display-"+(i+1)+".png"));
   Debug.Log("[qa] captured view="+(i+1));
   yield return new WaitForSecondsRealtime(.3f);
  }
  main.SelectView(0);
 }
 static string Argument(string key){var args=Environment.GetCommandLineArgs();int i=Array.IndexOf(args,key);return i>=0&&i+1<args.Length?args[i+1]:null;}
 void Update(){
  if(Time.unscaledTime<next)return;next=Time.unscaledTime+2;
  foreach(var item in FindObjectsOfType<CampusCarController>())
   Debug.Log("[runtime] car="+item.CarId+" position="+item.transform.position+" state="+item.State+" order="+item.OrderId+" connected="+item.Connected);
 }
}
