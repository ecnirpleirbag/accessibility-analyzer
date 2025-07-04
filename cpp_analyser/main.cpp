#include <iostream>
#include <string>
#include "pugixml.hpp"
#include "json.hpp"

using json = nlohmann::json;

// Count elements missing aria-label or role using pugixml
int count_missing_aria(const pugi::xml_document& doc) {
    int missing = 0;
    const char* tags[] = {"button", "a", "input", "div", "span"};
    for (const char* tag : tags) {
        std::string xpath = std::string("//") + tag;
        pugi::xpath_node_set nodes = doc.select_nodes(xpath.c_str());
        for (auto it = nodes.begin(); it != nodes.end(); ++it) {
            pugi::xml_node el = it->node();
            if (!el.attribute("aria-label") && !el.attribute("role")) {
                missing++;
            }
        }
    }
    return missing;
}

// Check heading structure using pugixml
int count_skipped_headings(const pugi::xml_document& doc) {
    int last_level = 0;
    int skipped = 0;
    pugi::xpath_node_set nodes = doc.select_nodes("//h1|//h2|//h3|//h4|//h5|//h6");
    for (auto it = nodes.begin(); it != nodes.end(); ++it) {
        std::string name = it->node().name();
        if (name.length() == 2 && name[0] == 'h') {
            int level = name[1] - '0';
            if (last_level && level > last_level + 1) {
                skipped++;
            }
            last_level = level;
        }
    }
    return skipped;
}

int main() {
    std::string html((std::istreambuf_iterator<char>(std::cin)), std::istreambuf_iterator<char>());
    pugi::xml_document doc;
    pugi::xml_parse_result result = doc.load_string(html.c_str(), pugi::parse_default | pugi::parse_fragment);
    if (!result) {
        json error = { {"error", std::string("Failed to parse HTML: ") + result.description() } };
        std::cout << error.dump() << std::endl;
        return 1;
    }
    int missing_aria = count_missing_aria(doc);
    int skipped_headings = count_skipped_headings(doc);
    json output = {
        {"missing_aria", missing_aria},
        {"skipped_headings", skipped_headings}
    };
    std::cout << output.dump() << std::endl;
    return 0;
} 