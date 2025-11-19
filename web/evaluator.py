"""
Nix evaluation engine using nix-eval-jobs
"""
import json
import subprocess
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DerivationInfo:
    """Information about a single derivation from evaluation"""
    attr: str
    drv_path: str
    outputs: Dict[str, str]  # output name -> output path
    name: str


@dataclass
class EvaluationResult:
    """Result of evaluating a flakeref"""
    success: bool
    derivations: List[DerivationInfo]
    error: Optional[str] = None


class NixEvaluator:
    """Evaluates Nix expressions using nix-eval-jobs"""

    def __init__(self, nix_eval_jobs_bin: str = "nix-eval-jobs"):
        self.nix_eval_jobs_bin = nix_eval_jobs_bin

    def evaluate_flakeref(self, flakeref: str) -> EvaluationResult:
        """
        Evaluate a flakeref using nix-eval-jobs

        Args:
            flakeref: A flake reference like "github:NixOS/nixpkgs/nixos-unstable#packages.x86_64-linux"

        Returns:
            EvaluationResult containing derivations or error
        """
        logger.info(f"Starting evaluation of flakeref: {flakeref}")

        try:
            # Run nix-eval-jobs
            # nix-eval-jobs --flake <flakeref>
            cmd = [
                self.nix_eval_jobs_bin,
                "--flake", flakeref,
                "--force-recurse",  # Recurse into attribute sets
                "--no-instantiate",
            ]

            logger.debug(f"Running command: {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            derivations = []
            errors = []

            # nix-eval-jobs outputs one JSON object per line
            for line in process.stdout:
                if not line.strip():
                    continue

                try:
                    obj = json.loads(line)

                    # nix-eval-jobs outputs derivation objects with drvPath
                    if "drvPath" in obj:
                        drv = self._parse_derivation(obj)
                        if drv:
                            derivations.append(drv)

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse nix-eval-jobs output line: {line[:100]}")
                    errors.append(f"JSON parse error: {str(e)}")
                except Exception as e:
                    logger.warning(f"Error processing line: {str(e)}")
                    errors.append(str(e))

            # Wait for process to complete
            stderr = process.stderr.read()
            returncode = process.wait()

            if returncode != 0 and not derivations:
                error_msg = f"nix-eval-jobs failed with code {returncode}: {stderr}"
                logger.error(error_msg)
                return EvaluationResult(
                    success=False,
                    derivations=[],
                    error=error_msg
                )

            # Log warnings but don't fail if we got some derivations
            if stderr:
                logger.warning(f"nix-eval-jobs stderr: {stderr}")

            logger.info(f"Evaluation completed successfully. Found {len(derivations)} derivations")

            return EvaluationResult(
                success=True,
                derivations=derivations,
                error="\n".join(errors) if errors else None
            )

        except FileNotFoundError:
            error_msg = f"nix-eval-jobs not found. Is it installed?"
            logger.error(error_msg)
            return EvaluationResult(
                success=False,
                derivations=[],
                error=error_msg
            )
        except Exception as e:
            error_msg = f"Unexpected error during evaluation: {str(e)}"
            logger.exception(error_msg)
            return EvaluationResult(
                success=False,
                derivations=[],
                error=error_msg
            )

    def _parse_derivation(self, obj: Dict) -> Optional[DerivationInfo]:
        """
        Parse a derivation object from nix-eval-jobs output

        Example input:
        {
          "attr": "",
          "attrPath": [],
          "drvPath": "/nix/store/xxx-hello-2.12.2.drv",
          "name": "hello-2.12.2",
          "outputs": {"out": "/nix/store/yyy-hello-2.12.2"},
          "system": "x86_64-linux"
        }
        """
        try:
            # Extract derivation path
            drv_path = obj.get("drvPath", "")
            if not drv_path:
                return None

            # Extract attribute path (use attrPath array if attr is empty)
            attr = obj.get("attr", "")
            if not attr and "attrPath" in obj:
                attr_path = obj.get("attrPath", [])
                if attr_path:
                    attr = ".".join(attr_path)

            # Extract name
            name = obj.get("name", "")

            # Extract outputs (dict of output_name -> output_path)
            outputs = obj.get("outputs", {})

            return DerivationInfo(
                attr=attr,
                drv_path=drv_path,
                outputs=outputs,
                name=name
            )
        except Exception as e:
            logger.warning(f"Failed to parse derivation object: {str(e)}")
            return None
