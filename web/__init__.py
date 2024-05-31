from collections import defaultdict
import json
import random
import typing as t
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas, crud, user_controller
from .db import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

origins = [
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

get_bearer_token = HTTPBearer(auto_error=False)

async def get_token(
    auth: t.Optional[HTTPAuthorizationCredentials] = Depends(get_bearer_token),
) -> str:
    if auth is not None:
        return auth.credentials
    else:
        return ""



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_user(username, token=None):
    if token is not None:
        user_controller.create_user(username, token)
    else:
        user_controller.create_user(username)



def get_drv_recap_or_404(session, drv_hash, full) -> schemas.DerivationAttestation:
    drv = session.query(models.Derivation).filter_by(drv_hash=drv_hash).one_or_none()
    if drv is None:
        raise HTTPException(status_code=404, detail="Not found")

    attestations = drv.attestations
    if (full):
        return attestations;

    attestation_outputs = defaultdict(dict)
    for attestation in attestations:
        if attestation.output_hash not in attestation_outputs[attestation.output_path].keys():
            attestation_outputs[attestation.output_path][attestation.output_hash] = 1
        else:
            attestation_outputs[attestation.output_path][attestation.output_hash] += 1

    return attestation_outputs

@app.get("/derivations/")
def get_derivations(db: Session = Depends(get_db)) -> schemas.DerivationList:
    return db.query(models.Derivation).all()

@app.get("/derivations/{drv_hash}")
def get_drv(drv_hash: str,
            full: bool = False,
            db: Session = Depends(get_db),
):
    return get_drv_recap_or_404(db, drv_hash, full)

@app.get("/derivations/{drv_hash}")
def get_drv_recap(drv_hash: str, db: Session = Depends(get_db)) -> schemas.DerivationAttestation:
    return get_drv_recap_or_404(db, drv_hash)

# Suggested rebuilds
@app.get("/reports/{name}/suggested")
def derivations_suggested_for_rebuilding(
    name: str,
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
):
    report = crud.report(db, name)
    if report == None:
        raise HTTPException(status_code=404, detail="Report not found")
    paths = report_out_paths(report)

    user = crud.get_user_with_token(db, token)
    suggestions = crud.suggest(db, paths, user)
    random.shuffle(suggestions)
    return suggestions[:50]

@app.post("/attestation/{drv_hash}")
def record_attestation(
    drv_hash: str,
    output_sha256_map: list[schemas.OutputHashPair],
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
):
    user = crud.get_user_with_token(db, token)
    if user == None:
        raise HTTPException(status_code=401, detail="User not found")

    crud.create_attestation(db, drv_hash, output_sha256_map, user)
    return {
        "Attestation accepted"
    }

@app.get("/attestations/by-output/{output_path}")
def attestations_by_out(output_path: str, db: Session = Depends(get_db)):
    return db.query(models.Attestation).filter_by(output_path="/nix/store/"+output_path).all()

def report_out_paths(report):
    paths = []
    root = report['metadata']['component']['bom-ref']
    paths.append(root)
    for component in report['components']:
        for prop in component['properties']:
            if prop['name'] == "nix:out_path":
                paths.append(prop['value'])
    return paths

@app.get("/reports")
def reports(db: Session = Depends(get_db)):
    reports = db.query(models.Report).all()
    names = []
    for report in reports:
        names.append(report.name)
    return names

def printtree(root, deps, results, cur_indent=0, seen=None):
  if seen is None:
    seen = {}
  if root in seen:
    return "  " * cur_indent + "...\n"
  seen[root] = True;

  result = "  " * cur_indent + root[11:];
  if root in results:
    result = result + " " + results[root] + "\n"
  else:
    result = result + "\n"
  for dep in deps:
      if dep['ref'] == root and 'dependsOn' in dep:
          for d in dep['dependsOn']:
              result += printtree(d, deps, results, cur_indent+2, seen)
              #result = result + "\n    " + d
  return result

def htmltree(root, deps, results):
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
    seen[root] = True;

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
  tree = generatetree(root, {})
  return '''
  <html>
  <head>
    <style>
      .tree{
        --spacing : 1.5rem;
        --radius  : 8px;
      }

      .tree li{
        display      : block;
        position     : relative;
        padding-left : calc(2 * var(--spacing) - var(--radius) - 2px);
      }
      
      .tree ul{
        margin-left  : calc(var(--radius) - var(--spacing));
        padding-left : 0;
      }
      
      .tree ul li{
        border-left : 2px solid #ddd;
      }
      
      .tree ul li:last-child{
        border-color : transparent;
      }
      
      .tree ul li::before{
        content      : '';
        display      : block;
        position     : absolute;
        top          : calc(var(--spacing) / -2);
        left         : -2px;
        width        : calc(var(--spacing) + 2px);
        height       : calc(var(--spacing) + 1px);
        border       : solid #ddd;
        border-width : 0 0 2px 2px;
      }
      
      .tree summary{
        display : block;
        cursor  : pointer;
      }
      
      .tree summary::marker,
      .tree summary::-webkit-details-marker{
        display : none;
      }
      
      .tree summary:focus{
        outline : none;
      }
      
      .tree summary:focus-visible{
        outline : 1px dotted #000;
      }
      
      .tree li::after,
      .tree summary::before{
        content       : '';
        display       : block;
        position      : absolute;
        top           : calc(var(--spacing) / 2 - var(--radius));
        left          : calc(var(--spacing) - var(--radius) - 1px);
        width         : calc(2 * var(--radius));
        height        : calc(2 * var(--radius));
        border-radius : 50%;
        background    : #ddd;
      }
      
    </style>
  </head>
  ''' + f'''
  <body>
    <ul class="tree">
    <li>
    {tree}
    </li>
    </ul>
  </body>
  </html>
'''

@app.get("/reports/{name}")
def report(
    name: str,
    accept: t.Optional[str] = Header(default="*/*"),
    db: Session = Depends(get_db),
):
    report = crud.report(db, name)
    if report == None:
        raise HTTPException(status_code=404, detail="Report not found")

    if 'application/vnd.cyclonedx+json' in accept:
        return Response(
            content=json.dumps(report),
            media_type='application/vnd.cyclonedx+json')

    if 'text/html' in accept:
        return Response(
            content='''
<html>
<head>
  <meta charset="utf-8"/>
  <!-- todo ship -->
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
  <!-- todo ship or replace -->
  <script src=" https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js "></script>
</head>
<body>
  <div id="main" style="width: 1000; height: 1000"></div>
  <script>
var option;
const myChart = echarts.init(document.getElementById('main'))
myChart.showLoading();
myChart.showLoading();
$.get(document.location.pathname + '/graph-data.json', function (webkitDep) {
  console.log('loaded', webkitDep);
  myChart.hideLoading();
  option = {
    color: webkitDep.color,
    legend: {
      data: webkitDep.legend
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        animation: false,
        label: {
          position: 'right',
          formatter: '{b}'
        },
        draggable: true,
        data: webkitDep.nodes.map(function (node, idx) {
          node.id = idx;
          node.value = 1;
          return node;
        }),
        categories: webkitDep.categories,
        force: {
          edgeLength: 5,
          repulsion: 20,
          gravity: 0.2
        },
        edges: webkitDep.links
      }
    ]
  };
  myChart.setOption(option);
});
  </script>
</body>
</html>
            ''',
            media_type='text/html')
    else:
        paths = report_out_paths(report)
        root = report['metadata']['component']['bom-ref']
        results = crud.path_summaries(db, paths)
        return Response(
            content=printtree(root, report['dependencies'], results),
            media_type='text/plain')

@app.get("/reports/{name}/graph-data.json")
def graph_data(
    name: str,
    db: Session = Depends(get_db),
):
    report = crud.report(db, name)
    if report == None:
        raise HTTPException(status_code=404, detail="Report not found")

    legend = [
        "No builds",
        "One build",
        "Partially reproduced",
        "Successfully reproduced",
        "Consistently nondeterministic",
    ];
    color = [
        "#eeeeee",
        "#aaaaaa",
        "#eeaaaa",
        "#00ee00",
        "#ee0000",
    ];
    categories = []
    for category in legend:
        categories.append({
            "name": category,
            "base": category,
            "keyword": {},
        })
    paths = report_out_paths(report)
    results = crud.path_summaries(db, paths)

    nodes = []
    for path in paths:
        nodes.append({
            "name": path,
            "category": results[path],
        })
    links = []
    for dep in report['dependencies']:
        for dependee in dep['dependsOn']:
            links.append({
                "source": paths.index(dep['ref']),
                "target": paths.index(dependee),
            })
    return {
            "type": "force",
            "legend": legend,
            "categories": categories,
            "color": color,
            "nodes": nodes,
            "links": links,
    }

@app.put("/reports/{name}")
def define_report(
    name: str,
    definition: schemas.ReportDefinition,
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
):
    user = crud.get_user_with_token(db, token)
    if user == None:
        raise HTTPException(status_code=401, detail="User not found")
    crud.define_report(db, name, definition.root)
    return {
        "Report defined"
    }
