#pragma once
#include <cstddef>
#include <string>
#include <unordered_map>

struct BuildingInfo {
    std::string stable_id;
    std::string mesh_id;
    std::string display_name;
    std::string map_label;
    double center_x = 0, center_y = 0;
    std::string navigation_status;
    std::string dock_node_id;
    double dock_x = 0, dock_y = 0;
    bool hasSimulationDock() const { return navigation_status == "simulation_dock"; }
};

class BuildingCatalog {
public:
    bool load(const std::string& path, std::string& error);
    const BuildingInfo* findById(const std::string& stable_id) const;
    size_t size() const { return buildings_.size(); }
private:
    std::unordered_map<std::string, BuildingInfo> buildings_;
};
