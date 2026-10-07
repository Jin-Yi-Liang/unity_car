#include "../include/building_catalog.h"
#include <cstdio>
int main(int argc, char** argv) {
    if (argc != 2 && argc != 3) {
        std::fprintf(stderr,"usage: catalog_lookup_run stable_id [catalog.tsv]\n"); return 2;
    }
    BuildingCatalog catalog;
    std::string error;
    if (!catalog.load(argc == 3 ? argv[2] : "data/buildings.tsv", error)) {
        std::fprintf(stderr,"%s\n",error.c_str()); return 1;
    }
    const BuildingInfo* item=catalog.findById(argv[1]);
    if (!item) { std::fprintf(stderr,"unknown building ID: %s\n",argv[1]); return 1; }
    std::printf("id=%s\nmesh=%s\nname=%s\nmap_label=%s\ncenter=%.3f,%.3f\nnavigation=%s\ndock_node=%s\n",
        item->stable_id.c_str(),item->mesh_id.c_str(),item->display_name.c_str(),item->map_label.c_str(),
        item->center_x,item->center_y,item->navigation_status.c_str(),item->dock_node_id.c_str());
    return 0;
}
