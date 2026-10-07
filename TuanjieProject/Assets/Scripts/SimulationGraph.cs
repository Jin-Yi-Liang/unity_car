using System;
using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

public sealed class SimulationGraph {
 public sealed class Edge { public string From, To; public List<Vector2> Points; public float Length; }
 public readonly Dictionary<string,Vector2> Nodes=new Dictionary<string,Vector2>();
 public readonly Dictionary<string,List<Edge>> Adjacent=new Dictionary<string,List<Edge>>();
 static readonly CultureInfo C=CultureInfo.InvariantCulture;
 static float F(string value){return float.Parse(value,C);}
 public static SimulationGraph Load(TextAsset asset){
  if(asset==null)throw new ArgumentNullException("asset");
  var graph=new SimulationGraph();
  foreach(string raw in asset.text.Split('\n')){
   string line=raw.Trim();if(line.Length==0||line[0]=='#')continue;
   string[] parts=line.Split('|');
   if(parts[0]=="N") {var p=new Vector2(F(parts[2]),F(parts[3]));graph.Nodes.Add(parts[1],p);graph.Adjacent.Add(parts[1],new List<Edge>());}
   else if(parts[0]=="E"){
    var edge=new Edge{From=parts[2],To=parts[3],Points=new List<Vector2>()};
    foreach(string token in parts[4].Split(';')){string[] xy=token.Split(':');edge.Points.Add(new Vector2(F(xy[0]),F(xy[1])));}
    for(int i=1;i<edge.Points.Count;i++)edge.Length+=Vector2.Distance(edge.Points[i-1],edge.Points[i]);
    graph.Adjacent[edge.From].Add(edge);graph.Adjacent[edge.To].Add(edge);
   }
  }
  return graph;
 }
 public string Nearest(Vector2 p,out float distance){
  string id=null;distance=float.MaxValue;
  foreach(var item in Nodes){float d=Vector2.Distance(p,item.Value);if(d<distance){distance=d;id=item.Key;}}
  return id;
 }
 public List<Vector2> Route(string start,string goal){
  var cost=new Dictionary<string,float>();var previous=new Dictionary<string,string>();var via=new Dictionary<string,Edge>();var pending=new HashSet<string>();
  foreach(string id in Nodes.Keys){cost[id]=float.PositiveInfinity;pending.Add(id);}cost[start]=0;
  while(pending.Count>0){
   string current=null;float best=float.PositiveInfinity;
   foreach(string id in pending)if(cost[id]<best){best=cost[id];current=id;}
   if(current==null||current==goal)break;pending.Remove(current);
   foreach(Edge edge in Adjacent[current]){string next=edge.From==current?edge.To:edge.From;float candidate=best+edge.Length;
    if(pending.Contains(next)&&candidate<cost[next]){cost[next]=candidate;previous[next]=current;via[next]=edge;}}
  }
  if(start!=goal&&!previous.ContainsKey(goal))throw new InvalidOperationException("No road route from "+start+" to "+goal);
  var ids=new List<string>();for(string id=goal;id!=start;id=previous[id])ids.Add(id);ids.Reverse();
  var points=new List<Vector2>{Nodes[start]};string from=start;
  foreach(string to in ids){Edge edge=via[to];if(edge.From==from){for(int i=1;i<edge.Points.Count;i++)points.Add(edge.Points[i]);}
   else{for(int i=edge.Points.Count-2;i>=0;i--)points.Add(edge.Points[i]);}from=to;}
  return points;
 }
}
