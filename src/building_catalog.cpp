#include "../include/building_catalog.h"
#include <cmath>
#include <fstream>
#include <sstream>
#include <utility>
#include <vector>

namespace {
std::vector<std::string> fields(const std::string& line) {
    std::vector<std::string> result;
    std::stringstream stream(line);
    std::string field;
    while (std::getline(stream, field, '\t')) result.push_back(field);
    return result;
}
bool parseNumber(const std::string& text, double& value) {
    try {
        size_t used = 0;
        value = std::stod(text, &used);
        return used == text.size() && std::isfinite(value);
    } catch (...) { return false; }
}
}

bool BuildingCatalog::load(const std::string& path, std::string& error) {
    std::ifstream file(path);
    if (!file) { error = "cannot open building catalog: " + path; return false; }
    std::string line;
    if (!std::getline(file, line) ||
        line != "stable_id\tmesh_id\tdisplay_name\tmap_label\tcenter_x\tcenter_y\tnavigation_status\tdock_node_id\tdock_x\tdock_y") {
        error = "invalid building catalog header"; return false;
    }
    std::unordered_map<std::string, BuildingInfo> parsed;
    size_t line_number = 1;
    while (std::getline(file, line)) {
        ++line_number;
        auto f = fields(line);
        if (f.size() != 10 || f[0].empty() || f[1].empty() || f[2].empty() || f[3].empty() ||
            (f[6] != "unassigned" && f[6] != "simulation_dock")) {
            error = "invalid building catalog row " + std::to_string(line_number); return false;
        }
        BuildingInfo item;
        item.stable_id=f[0]; item.mesh_id=f[1]; item.display_name=f[2]; item.map_label=f[3];
        item.navigation_status=f[6]; item.dock_node_id=f[7];
        if (!parseNumber(f[4],item.center_x) || !parseNumber(f[5],item.center_y) ||
            !parseNumber(f[8],item.dock_x) || !parseNumber(f[9],item.dock_y) ||
            (item.hasSimulationDock() && item.dock_node_id == "-") ||
            (!item.hasSimulationDock() && item.dock_node_id != "-")) {
            error = "invalid coordinates or dock in row " + std::to_string(line_number); return false;
        }
        if (!parsed.emplace(item.stable_id,item).second) {
            error = "duplicate building ID: " + item.stable_id; return false;
        }
    }
    if (parsed.empty()) { error = "empty building catalog"; return false; }
    buildings_ = std::move(parsed);
    error.clear();
    return true;
}

const BuildingInfo* BuildingCatalog::findById(const std::string& stable_id) const {
    auto it = buildings_.find(stable_id);
    return it == buildings_.end() ? nullptr : &it->second;
}
