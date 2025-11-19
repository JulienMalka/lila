"""
Report service - Business logic for report generation and processing
"""
import re
from collections import defaultdict
from typing import Dict, List


class ReportService:
    """Service for processing report data"""

    @staticmethod
    def get_status_icon(status: str) -> str:
        """Get emoji icon for reproducibility status"""
        # Simplified icons: green check for reproducible, red X for not reproducible, question mark for unknown
        if status == "Successfully reproduced":
            return "✅"
        elif status in ("Consistently nondeterministic", "Partially reproduced"):
            return "❌"
        else:  # "No builds" or "One build"
            return "❔"

    @staticmethod
    def number_and_percentage(n: int, total: int) -> str:
        """Format number with percentage"""
        if total == 0:
            return f"{n} (0%)"
        return f"{n} ({str(100*n/total)[:4]}%)"

    @staticmethod
    def get_external_links(derivation: str, link_patterns: List) -> List[str]:
        """Get external links for a derivation based on patterns"""
        name = derivation[44:]  # Strip /nix/store/ prefix
        return [lp.link for lp in link_patterns if re.match(lp.pattern, name)]

    @staticmethod
    def find_multi_affected(lists: list) -> list:
        """Find items that appear in multiple lists"""
        seen_once = []
        seen_multi = []
        for l in lists:
            for i in l:
                if i not in seen_multi:
                    if i in seen_once:
                        seen_multi.append(i)
                    else:
                        seen_once.append(i)
        return seen_multi

    def group_derivations(self, derivations: List[str], link_patterns: List, output_to_drv_map: Dict = None) -> Dict:
        """Group derivations by external link patterns"""
        all_links = [self.get_external_links(d, link_patterns) for d in derivations]
        groups = {}
        groups[""] = {
            'label': "",
            'items': [],
        }

        for link in self.find_multi_affected(all_links):
            groups[link] = {
                'label': link,
                'link': link,
                'items': [],
            }

        for d in derivations:
            links = self.get_external_links(d, link_patterns)
            # Extract derivation hash from store path /nix/store/hash-name
            # Use output_to_drv_map if available, otherwise extract from path
            if output_to_drv_map and d in output_to_drv_map:
                drv_hash = output_to_drv_map[d]
            else:
                drv_hash = d[11:] if d.startswith('/nix/store/') else d
            item = {
                "name": d[44:],
                "drv": d,
                "link": f"/derivations/{drv_hash}",
                "external_links": links,
            }
            if links and links[0] in groups:
                groups[links[0]]['items'].append(item)
            else:
                groups[""]['items'].append(item)

        return groups

    def prepare_report_view_data(self, root: str, deps: List, results: Dict, link_patterns: List, output_to_drv_map: Dict = None) -> Dict:
        """
        Prepare all data needed for report view
        Returns dict that can be passed directly to template
        """
        # Group results by type
        results_by_type = defaultdict(list)
        for drv in results:
            results_by_type[results[drv]].append(drv)

        # Calculate statistics
        total = len(results)
        count_reproducible = len(results_by_type["Successfully reproduced"])
        count_not_reproducible = len(results_by_type["Consistently nondeterministic"]) + len(results_by_type["Partially reproduced"])
        count_not_checked = len(results_by_type["No builds"]) + len(results_by_type["One build"])

        n_reproducible = self.number_and_percentage(count_reproducible, total)
        n_not_reproducible = self.number_and_percentage(count_not_reproducible, total)
        n_not_checked = self.number_and_percentage(count_not_checked, total)

        # Group derivations
        reproducible = self.group_derivations(
            results_by_type["Successfully reproduced"],
            link_patterns,
            output_to_drv_map
        )
        not_reproducible = self.group_derivations(
            results_by_type["Consistently nondeterministic"] + results_by_type["Partially reproduced"],
            link_patterns,
            output_to_drv_map
        )
        not_checked_one_build = self.group_derivations(
            results_by_type["One build"],
            link_patterns,
            output_to_drv_map
        )
        not_checked_no_builds = self.group_derivations(
            results_by_type["No builds"],
            link_patterns,
            output_to_drv_map
        )

        # Generate tree HTML (we'll convert this to template later)
        # Check if this is a flat evaluation report (no dependencies) or a hierarchical dependency tree
        has_dependencies = any(dep.get('dependsOn', []) for dep in deps)

        if has_dependencies:
            # Traditional dependency tree - use root as entry point
            tree_html = self._generate_tree_html(root, deps, results, output_to_drv_map=output_to_drv_map)
        else:
            # Flat evaluation report - show all components
            tree_html = self._generate_flat_tree_html(deps, results, output_to_drv_map=output_to_drv_map)

        return {
            "title": root[44:],
            "reproducible_n": n_reproducible,
            "reproducible": reproducible,
            "count_reproducible": count_reproducible,
            "not_reproducible_n": n_not_reproducible,
            "not_reproducible": not_reproducible,
            "count_not_reproducible": count_not_reproducible,
            "not_checked_n": n_not_checked,
            "not_checked_one_build": not_checked_one_build,
            "not_checked_no_builds": not_checked_no_builds,
            "count_not_checked": count_not_checked,
            "tree": tree_html,
        }

    def _generate_flat_tree_html(self, deps: List, results: Dict, output_to_drv_map: Dict = None) -> str:
        """Generate HTML for flat list of evaluation outputs (no dependency relationships)"""
        html = '<summary>Evaluation Outputs</summary>\n<ul>'

        # Sort dependencies by reproducibility status and name
        sorted_deps = sorted(deps, key=lambda d: (
            # Sort order: reproducible first, then partially/nondeterministic, then unchecked
            0 if results.get(d['ref']) == "Successfully reproduced" else
            1 if results.get(d['ref']) in ("Partially reproduced", "Consistently nondeterministic") else
            2,
            d['ref']  # Then alphabetically
        ))

        for dep in sorted_deps:
            ref = dep['ref']

            # Extract derivation hash
            drv_hash = None
            if output_to_drv_map and ref in output_to_drv_map:
                drv_hash = output_to_drv_map[ref]
            elif ref.startswith('/nix/store/'):
                drv_hash = ref[11:]

            html += '<li><details open>'
            html += f'<summary title="{ref}">'

            # Add status icon
            if ref in results:
                icon = self.get_status_icon(results[ref])
                status_text = results[ref]
                html += f'<span title="{status_text}">{icon}</span>'

            # Add link to derivation detail page
            name = ref[44:] if len(ref) > 44 else ref
            if drv_hash:
                html += f'<a href="/derivations/{drv_hash}" class="text-blue-600 hover:text-blue-800">{name}</a>'
            else:
                html += name

            html += '</summary>'
            html += '</details></li>\n'

        html += '</ul>'
        return html

    def _generate_tree_html(self, root: str, deps: List, results: Dict, seen=None, output_to_drv_map: Dict = None) -> str:
        """Generate HTML tree structure (temporary - will move to template)"""
        if seen is None:
            seen = {}

        if root in seen:
            return f'<summary title="{root}">...</summary>'

        seen[root] = True

        # Extract derivation hash from store path
        # Use output_to_drv_map if available, otherwise extract from path
        drv_hash = None
        if output_to_drv_map and root in output_to_drv_map:
            drv_hash = output_to_drv_map[root]
        elif root.startswith('/nix/store/'):
            drv_hash = root[11:]  # Remove /nix/store/ prefix

        html = f'<summary title="{root}">'
        if root in results:
            icon = self.get_status_icon(results[root])
            status_text = results[root]
            html += f'<span title="{status_text}">{icon}</span>'

            # Add link to derivation detail page
            if drv_hash:
                html += f'<a href="/derivations/{drv_hash}" class="text-blue-600 hover:text-blue-800">{root[44:]}</a> '
            else:
                html += f'{root[44:]} '
        else:
            if drv_hash:
                html += f'<a href="/derivations/{drv_hash}" class="text-blue-600 hover:text-blue-800">{root[44:]}</a>'
            else:
                html += root[44:]
        html += "</summary>\n<ul>"

        for dep in deps:
            if dep['ref'] == root and 'dependsOn' in dep:
                for d in dep['dependsOn']:
                    html += f'<li><details class="{d}" open>'
                    html += self._generate_tree_html(d, deps, results, seen, output_to_drv_map)
                    html += "</details></li>"

        html += "</ul>"
        return html

    @staticmethod
    def generate_tree_text(root: str, deps: List, results: Dict, cur_indent=0, seen=None) -> str:
        """Generate plain text tree representation"""
        if seen is None:
            seen = {}

        if root in seen:
            return "  " * cur_indent + "...\n"

        seen[root] = True

        result = "  " * cur_indent + root[11:]
        if root in results:
            result = result + " " + results[root] + "\n"
        else:
            result = result + "\n"

        for dep in deps:
            if dep['ref'] == root and 'dependsOn' in dep:
                for d in dep['dependsOn']:
                    result += ReportService.generate_tree_text(d, deps, results, cur_indent+2, seen)

        return result
