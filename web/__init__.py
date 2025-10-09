from collections import defaultdict
import json
import pathlib
import random
import re
import typing as t
from fastapi import Depends, FastAPI, Header, HTTPException, Response, Request
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas, crud, user_controller
from .db import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI()
thispath = pathlib.Path(__file__).parent.resolve()
app.mount("/static", StaticFiles(directory=str(thispath) + "/static"), name="static")

templates = Jinja2Templates(directory=str(thispath) + "/templates")

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

def htmlview(root, deps, results, link_patterns):
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

  # Manually construction HTML for now,
  # could be template-ified further
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

  def number_and_percentage(n: int, total: int) -> int:
    return f"{n} ({str(100*n/total)[:4]}%)"

  def external_links(derivation: str) -> [ str ]:
      name = derivation[44:]
      return [ lp.link for lp in link_patterns if re.match(lp.pattern, name) ]

  def generate_list(derivations: list) -> dict:
      return { d: {
                    "name": d[44:],
                    "link": f"/attestations/by-output/{d[11:]}",
                    "external_links": external_links(d)
                  } for d in derivations }

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

@app.get("/reports/{name}")
async def report(
    request: Request,
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

    paths = report_out_paths(report)

    root = report['metadata']['component']['bom-ref']
    results = crud.path_summaries(db, paths)

    if 'text/html' in accept:
        link_patterns = get_link_patterns(db)
        return templates.TemplateResponse(
            request = request, name="report.html", context=htmlview(root, report['dependencies'], results, link_patterns)
        )
    else:
        return Response(
            content=printtree(root, report['dependencies'], results),
            media_type='text/plain')

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

@app.get("/link_patterns")
def get_link_patterns(db: Session = Depends(get_db)):
    return db.query(models.LinkPattern).all()

@app.post("/link_patterns")
def post_link_pattern(
    pattern: str,
    link: str,
    token: str = Depends(get_token),
    db: Session = Depends(get_db)
):
    user = crud.get_user_with_token(db, token)
    if user == None:
        raise HTTPException(status_code=401, detail="User not found")
    crud.add_link_pattern(db, pattern, link)
    return "OK"

@app.get("/signatures/{user_name}/{output_digest}.narinfo")
def nix_cache_info(user_name: str,
                   output_digest: str,
                   db: Session = Depends(get_db),
):
    user = db.query(models.User).filter_by(name=user_name).one_or_none()
    if user == None:
        raise HTTPException(status_code=401, detail="User not found")
    attestations = db.query(models.Attestation).filter_by(output_digest=output_digest,user_id=user.id).all()
    if len(attestations) == 0:
        raise HTTPException(status_code=404, detail="Not found")
    attestation = attestations[0]
    return Response(content=f"""StorePath: /nix/store/{attestation.output_digest}-{attestation.output_name}
URL: no
NarHash: {attestation.output_hash}
NarSize: 1
Sig: {attestation.output_sig}
""", media_type="text/x-nix-narinfo")
