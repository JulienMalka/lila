"""
Report view routes
"""
from collections import defaultdict
import json
import random
import re
import typing as t
from fastapi import APIRouter, Depends, Header, HTTPException, Response, Request
from sqlalchemy.orm import Session

from .. import crud, models
from ..common import get_db, get_token, templates

router = APIRouter()


def report_out_paths(report):
    """Extract output paths from report"""
    paths = []
    for component in report['components']:
        for prop in component['properties']:
            if prop['name'] == "nix:out_path":
                paths.append(prop['value'])
    return paths


def report_elements(report):
    """Extract report elements with their properties"""
    paths = {}
    for component in report['components']:
        item = {}
        for prop in component['properties']:
            if prop['name'] == "nix:out_path":
                item['out_path'] = prop['value']
            elif prop['name'] == "nix:output_path":
                item['out_path'] = prop['value']
            elif prop['name'] == "nix:drv_path":
                item['drv_path'] = prop['value']
            elif prop['name'] == "nix:output":
                item['output'] = prop['value']
        if 'out_path' in item:
            paths[item['out_path']] = item
    return paths


def printtree(root, deps, results, cur_indent=0, seen=None):
    """Generate text tree view of dependencies"""
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
                result += printtree(d, deps, results, cur_indent+2, seen)
    return result


def htmlview(root, deps, results, link_patterns):
    """Generate HTML view of report with reproducibility status"""

    def icon(result):
        if result == "No builds":
            return "❔ "
        elif result == "One build":
            return "❎ "
        elif result == "Partially reproduced":
            return "❕ "
        elif result == "Successfully reproduced":
            return "✅ "
        elif result == "Consistently nondeterministic":
            return "❌ "
        else:
            return ""

    def generatetree(root, seen):
        if root in seen:
            return f'<summary title="{root}">...</summary>'
        seen[root] = True

        result = f'<summary title="{root}">'
        if root in results:
            result = result + f'<span title="{results[root]}">' + icon(results[root]) + "</span>" + root[44:] + " "
        else:
            result = result + root[44:]
        result = result + "</summary>\n"
        result = result + "<ul>"
        for dep in deps:
            if dep['ref'] == root and 'dependsOn' in dep:
                for d in dep['dependsOn']:
                    result += f'<li><details class="{d}" open>'
                    result += generatetree(d, seen)
                    result += "</details></li>"
        result = result + "</ul>"
        return result

    def number_and_percentage(n: int, total: int) -> str:
        return f"{n} ({str(100*n/total)[:4]}%)"

    def external_links(derivation: str) -> list:
        name = derivation[44:]
        return [lp.link for lp in link_patterns if re.match(lp.pattern, name)]

    def multi(lists: list) -> list:
        seen_once = []
        seen_multi = []
        for l in lists:
            for i in l:
                if not i in seen_multi:
                    if i in seen_once:
                        seen_multi.append(i)
                    else:
                        seen_once.append(i)
        return seen_multi

    def generate_list(derivations: list) -> dict:
        all_links = [external_links(d) for d in derivations]
        groups = {}
        groups[""] = {
            'label': "",
            'items': [],
        }
        for link in multi(all_links):
            groups[link] = {
                'label': link,
                'link': link,
                'items': [],
            }

        for d in derivations:
            links = external_links(d)
            item = {
                "name": d[44:],
                "drv": d,
                "link": f"/attestations/by-output/{d[11:]}",
                "external_links": links,
            }
            if links and links[0] in groups:
                groups[links[0]]['items'].append(item)
            else:
                groups[""]['items'].append(item)

        return groups

    def generate_lists():
        resultsbytype = defaultdict(list)
        for drv in results:
            resultsbytype[results[drv]].append(drv)
        n_not_reproducible = number_and_percentage(
            len(resultsbytype["Consistently nondeterministic"]) + len(resultsbytype["Partially reproduced"]),
            len(results)
        )
        not_reproducible = generate_list(resultsbytype["Consistently nondeterministic"] + resultsbytype["Partially reproduced"])
        n_not_checked = number_and_percentage(
            len(resultsbytype["No builds"]) + len(resultsbytype["One build"]),
            len(results)
        )
        not_checked_one_build = generate_list(resultsbytype["One build"])
        not_checked_no_builds = generate_list(resultsbytype["No builds"])
        return n_not_reproducible, not_reproducible, n_not_checked, not_checked_one_build, not_checked_no_builds

    not_reproducible_n, not_reproducible, not_checked_n, not_checked_one_build, not_checked_no_builds = generate_lists()

    return {
        "title": root[44:],
        "not_reproducible_n": not_reproducible_n,
        "not_reproducible": not_reproducible,
        "not_checked_n": not_checked_n,
        "not_checked_one_build": not_checked_one_build,
        "not_checked_no_builds": not_checked_no_builds,
        "tree": generatetree(root, {}),
    }


@router.get("")
def reports(db: Session = Depends(get_db)):
    """List all reports"""
    reports = db.query(models.Report).all()
    names = []
    for report in reports:
        names.append(report.name)
    return names


# Suggested rebuilds - deprecated API
@router.get("/{name}/suggested")
def derivations_suggested_for_rebuilding(
    name: str,
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
):
    """Get suggested derivations for rebuilding (deprecated)"""
    report = crud.report(db, name)
    if report == None:
        raise HTTPException(status_code=404, detail="Report not found")
    elements = report_elements(report)

    user = crud.get_user_with_token(db, token)
    suggestions = list(crud.suggest(db, elements, user).keys())
    random.shuffle(suggestions)
    return suggestions[:50]


# Suggested rebuilds
@router.get("/{name}/suggest")
def suggest_derivations_for_rebuilding(
    name: str,
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
):
    """Get suggested derivations for rebuilding"""
    report = crud.report(db, name)
    if report == None:
        raise HTTPException(status_code=404, detail="Report not found")
    elements = report_elements(report)

    user = crud.get_user_with_token(db, token)
    suggestions = list(crud.suggest(db, elements, user).values())
    random.shuffle(suggestions)
    return suggestions[:50]


@router.get("/{name}")
async def report(
    request: Request,
    name: str,
    accept: t.Optional[str] = Header(default="*/*"),
    db: Session = Depends(get_db),
):
    """Get a specific report in various formats (HTML, JSON, text)"""
    report = crud.report(db, name)
    if report == None:
        raise HTTPException(status_code=404, detail="Report not found")

    if 'application/vnd.cyclonedx+json' in accept:
        return Response(
            content=json.dumps(report),
            media_type='application/vnd.cyclonedx+json')

    paths = report_out_paths(report)
    root = report['metadata']['component']['bom-ref']
    results = crud.path_summaries(db, paths)

    if 'text/html' in accept:
        link_patterns = db.query(models.LinkPattern).all()
        return templates.TemplateResponse(
            request=request,
            name="report.html",
            context=htmlview(root, report['dependencies'], results, link_patterns)
        )
    else:
        return Response(
            content=printtree(root, report['dependencies'], results),
            media_type='text/plain')


@router.put("/{name}")
def define_report(
    name: str,
    definition: dict,  # schemas.ReportDefinition if you have it
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
):
    """Define or update a report"""
    user = crud.get_user_with_token(db, token)
    if user == None:
        raise HTTPException(status_code=401, detail="User not found")
    crud.define_report(db, name, definition)
    return {
        "Report defined"
    }
