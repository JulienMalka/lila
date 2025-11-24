#!/usr/bin/env python3
"""
Generate synthetic test data for Lila frontend testing.

This script creates realistic test data including:
- Multiple jobsets
- Evaluations with various states
- Derivations with different reproducibility outcomes
- Multiple attestations from different builders
"""

import random
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from web import models

# Configuration
NUM_JOBSETS = 5
NUM_EVALUATIONS_PER_JOBSET = 10
BASE_DERIVATIONS_PER_EVAL = 15  # Starting number of derivations
DERIVATION_GROWTH_PER_EVAL = 3  # How many more derivations each subsequent eval has
NUM_USERS = 8
NUM_ATTESTATIONS_PER_DRV = 3  # Average

# Sample data
JOBSET_NAMES = [
    "nixpkgs-unstable",
    "nixos-23.11",
    "nixos-24.05",
    "python-packages",
    "rust-packages",
]

PACKAGE_NAMES = [
    "hello", "gcc", "python3", "nodejs", "rust", "go", "cmake",
    "git", "vim", "emacs", "firefox", "chromium", "libreoffice",
    "postgresql", "mysql", "redis", "nginx", "apache", "docker",
    "kubernetes", "terraform", "ansible", "jenkins", "gitlab",
    "prometheus", "grafana", "elasticsearch", "mongodb", "cassandra",
]

USER_NAMES = [
    "builder-01", "builder-02", "builder-03", "builder-04",
    "ci-server-a", "ci-server-b", "community-alice", "community-bob",
]

JOBSET_DESCRIPTIONS = [
    "NixOS unstable channel - bleeding edge packages",
    "NixOS 23.11 stable release",
    "NixOS 24.05 stable release",
    "Python package collection",
    "Rust package collection",
]


def random_hash(length=32):
    """Generate a random hash-like string."""
    return hashlib.sha256(random.randbytes(32)).hexdigest()[:length]


def random_nix_hash():
    """Generate a random Nix-style base32 hash."""
    chars = "0123456789abcdfghijklmnpqrsvwxyz"
    return ''.join(random.choice(chars) for _ in range(32))


def random_signature(user_name):
    """Generate a fake Nix-style signature."""
    # Nix signatures look like: key-name:base64-signature
    import base64
    sig_data = base64.b64encode(random.randbytes(64)).decode('ascii')
    return f"{user_name}:{sig_data}"


def random_date(start_days_ago=365, end_days_ago=0):
    """Generate a random datetime within a range."""
    start = datetime.now() - timedelta(days=start_days_ago)
    end = datetime.now() - timedelta(days=end_days_ago)
    delta = end - start
    random_days = random.random() * delta.total_seconds()
    return start + timedelta(seconds=random_days)


def generate_drv_path(package_name, version):
    """Generate a realistic derivation path."""
    hash_part = random_nix_hash()
    return f"{hash_part}-{package_name}-{version}.drv"


def generate_output_path(package_name, version, output_name=None):
    """Generate a realistic output path."""
    hash_part = random_nix_hash()
    suffix = f"-{output_name}" if output_name and output_name != "out" else ""
    return f"/nix/store/{hash_part}-{package_name}-{version}{suffix}"


def generate_output_paths(package_name, version):
    """
    Generate output paths for a derivation.
    Most derivations have just 'out', but some have multiple outputs.
    """
    # 70% chance of single output, 30% chance of multiple outputs
    if random.random() < 0.7:
        return {"out": generate_output_path(package_name, version)}

    # Multiple outputs - pick from common combinations
    output_combinations = [
        ["out", "dev"],
        ["out", "lib"],
        ["out", "dev", "lib"],
        ["out", "doc"],
        ["out", "dev", "doc"],
        ["out", "bin", "lib"],
        ["out", "dev", "lib", "doc"],
    ]
    outputs = random.choice(output_combinations)
    return {name: generate_output_path(package_name, version, name) for name in outputs}


def random_version():
    """Generate a random version number."""
    major = random.randint(1, 10)
    minor = random.randint(0, 20)
    patch = random.randint(0, 50)
    return f"{major}.{minor}.{patch}"


def generate_cyclonedx_sbom(derivations_data):
    """
    Generate a CycloneDX SBOM structure for an evaluation.

    Args:
        derivations_data: List of tuples (package_name, version, drv_hash, output_paths)

    Returns:
        dict: CycloneDX SBOM structure
    """
    components = []
    all_out_paths = []

    for pkg_name, version, drv_hash, output_paths in derivations_data:
        # Get the main output path (usually "out")
        main_out = output_paths.get("out", list(output_paths.values())[0])
        all_out_paths.append(main_out)

        component = {
            "type": "library",
            "name": pkg_name,
            "version": version,
            "purl": f"pkg:nix/{pkg_name}@{version}",
            "bom-ref": main_out,
            "properties": [
                {
                    "name": "nix:derivation",
                    "value": drv_hash
                },
                {
                    "name": "nix:out_path",
                    "value": main_out
                },
                {
                    "name": "nix:outputs",
                    "value": json.dumps(output_paths)
                }
            ]
        }
        components.append(component)

    # Generate dependency relationships (create a tree-like structure)
    dependencies = []
    if len(all_out_paths) > 1:
        # Create a simple dependency tree:
        # First item is root, depends on a few others
        # Those depend on a few more, etc.
        root_path = all_out_paths[0]
        remaining = all_out_paths[1:]

        # Root depends on 2-4 items
        root_deps = remaining[:min(4, len(remaining))]
        dependencies.append({
            "ref": root_path,
            "dependsOn": root_deps
        })

        # Each of those depends on 1-3 others (if available)
        used = set(root_deps)
        available = [p for p in remaining if p not in used]

        for dep in root_deps:
            if available:
                num_deps = min(random.randint(1, 3), len(available))
                sub_deps = random.sample(available, num_deps)
                dependencies.append({
                    "ref": dep,
                    "dependsOn": sub_deps
                })
                used.update(sub_deps)
                available = [p for p in available if p not in used]

        # Add remaining items as leaf nodes with no dependencies
        for path in available:
            dependencies.append({
                "ref": path,
                "dependsOn": []
            })

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "tools": [
                {
                    "name": "lila-test-generator",
                    "version": "1.0.0"
                }
            ],
            "component": {
                "bom-ref": all_out_paths[0] if all_out_paths else ""
            }
        },
        "components": components,
        "dependencies": dependencies
    }

    return sbom


def reproducibility_outcome():
    """
    Determine reproducibility outcome with realistic probabilities.

    Returns: (num_unique_hashes, num_attestations)
    """
    outcome = random.choices(
        ['reproducible', 'partial', 'nondeterministic', 'one_build', 'no_builds'],
        weights=[0.6, 0.1, 0.15, 0.1, 0.05],
        k=1
    )[0]

    if outcome == 'reproducible':
        # All builds match
        num_attestations = random.randint(3, 8)
        return 1, num_attestations
    elif outcome == 'partial':
        # Some builds match, some don't
        num_attestations = random.randint(3, 8)
        num_unique = random.randint(2, min(3, num_attestations))
        return num_unique, num_attestations
    elif outcome == 'nondeterministic':
        # Most or all builds differ
        num_attestations = random.randint(3, 8)
        num_unique = random.randint(2, num_attestations)
        return num_unique, num_attestations
    elif outcome == 'one_build':
        return 1, 1
    else:  # no_builds
        return 0, 0


def main():
    # Connect to database
    db_path = Path(__file__).parent.parent / "web" / "hashes.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Session = sessionmaker(bind=engine)
    session = Session()

    print("Generating synthetic test data...")

    # Create users
    print(f"\nCreating {NUM_USERS} users...")
    users = []
    for name in USER_NAMES:
        user = models.User(name=name)
        session.add(user)
        users.append(user)
    session.commit()
    print(f"Created {len(users)} users")

    # Create jobsets
    print(f"\nCreating {NUM_JOBSETS} jobsets...")
    jobsets = []
    for i, name in enumerate(JOBSET_NAMES[:NUM_JOBSETS]):
        jobset = models.Jobset(
            name=name,
            description=JOBSET_DESCRIPTIONS[i % len(JOBSET_DESCRIPTIONS)],
            enabled=random.choice([True, True, True, False]),  # 75% enabled
        )
        session.add(jobset)
        jobsets.append(jobset)
    session.commit()
    print(f"Created {len(jobsets)} jobsets")

    # Create evaluations, derivations, and attestations
    total_evaluations = 0
    total_derivations = 0
    total_attestations = 0

    for jobset in jobsets:
        print(f"\nGenerating data for jobset '{jobset.name}'...")

        for eval_num in range(1, NUM_EVALUATIONS_PER_JOBSET + 1):
            # First, generate all derivations data for the SBOM
            derivations_data = []
            eval_derivations = []

            # Number of derivations grows over time
            num_derivations = BASE_DERIVATIONS_PER_EVAL + (eval_num - 1) * DERIVATION_GROWTH_PER_EVAL

            for _ in range(num_derivations):
                package_name = random.choice(PACKAGE_NAMES)
                version = random_version()
                drv_hash = generate_drv_path(package_name, version)
                output_paths = generate_output_paths(package_name, version)

                derivations_data.append((package_name, version, drv_hash, output_paths))

            # Generate SBOM from derivations data
            sbom = generate_cyclonedx_sbom(derivations_data)

            # Generate a random upload date (more recent evaluations have higher eval_num)
            # Spread evaluations over the last 180 days
            days_ago = 180 - (eval_num * 180 // NUM_EVALUATIONS_PER_JOBSET)
            upload_date = random_date(start_days_ago=days_ago + 10, end_days_ago=max(0, days_ago - 10))

            # Create evaluation with SBOM
            evaluation = models.Evaluation(
                jobset_id=jobset.id,
                definition_sbom=json.dumps(sbom),
                uploaded_at=upload_date,
            )
            session.add(evaluation)
            session.commit()
            total_evaluations += 1

            # Now create the actual derivations and link them to the evaluation
            for package_name, version, drv_hash, output_paths in derivations_data:
                # Check if derivation already exists
                derivation = session.query(models.Derivation).filter_by(
                    drv_hash=drv_hash
                ).first()

                if not derivation:
                    derivation = models.Derivation(drv_hash=drv_hash)
                    session.add(derivation)
                    session.commit()
                    total_derivations += 1

                # Create evaluation-derivation relationship
                eval_drv = models.EvaluationDerivation(
                    evaluation_id=evaluation.id,
                    derivation_id=derivation.id,
                )
                session.add(eval_drv)
                eval_derivations.append((derivation, output_paths))

                # Generate attestations for each output (each output has independent reproducibility)
                for output_key, output_path in output_paths.items():
                    # Each output gets its own reproducibility outcome
                    num_unique_hashes, num_attestations = reproducibility_outcome()

                    if num_attestations > 0:
                        # Generate unique output hashes for this output
                        output_hashes = [random_nix_hash() for _ in range(num_unique_hashes)]

                        for _ in range(num_attestations):
                            # Pick a hash (biased towards first one for reproducible builds)
                            if num_unique_hashes == 1:
                                output_hash = output_hashes[0]
                            else:
                                # Distribute somewhat unevenly
                                weights = [2] + [1] * (num_unique_hashes - 1)
                                output_hash = random.choices(output_hashes, weights=weights)[0]

                            # Extract digest and name from output path
                            # /nix/store/hash-name -> hash, name
                            path_parts = output_path.replace("/nix/store/", "").split("-", 1)
                            output_digest = path_parts[0]
                            output_name = path_parts[1] if len(path_parts) > 1 else package_name

                            user = random.choice(users)
                            attestation = models.Attestation(
                                drv_id=derivation.id,
                                user_id=user.id,
                                output_digest=output_digest,
                                output_name=output_name,
                                output_hash=output_hash,
                                output_path=output_path,
                                output_sig=random_signature(user.name),
                            )
                            session.add(attestation)
                            total_attestations += 1

            session.commit()

        print(f"  Created {NUM_EVALUATIONS_PER_JOBSET} evaluations")
        print(f"  Derivations per eval: {BASE_DERIVATIONS_PER_EVAL} -> {BASE_DERIVATIONS_PER_EVAL + (NUM_EVALUATIONS_PER_JOBSET - 1) * DERIVATION_GROWTH_PER_EVAL}")

    # Create some link patterns
    print("\nCreating link patterns...")
    link_patterns = [
        {
            "pattern": ".*-python.*",
            "link": "https://github.com/NixOS/nixpkgs/issues?q=python",
        },
        {
            "pattern": ".*-rust.*",
            "link": "https://github.com/NixOS/nixpkgs/issues?q=rust",
        },
        {
            "pattern": ".*-gcc.*",
            "link": "https://gcc.gnu.org/bugzilla/",
        },
    ]

    for lp_data in link_patterns:
        link_pattern = models.LinkPattern(
            pattern=lp_data["pattern"],
            link=lp_data["link"],
        )
        session.add(link_pattern)
    session.commit()
    print(f"Created {len(link_patterns)} link patterns")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Users:         {len(users)}")
    print(f"Jobsets:       {len(jobsets)}")
    print(f"Evaluations:   {total_evaluations}")
    print(f"Derivations:   {total_derivations} (unique)")
    print(f"Attestations:  {total_attestations}")
    print(f"Link Patterns: {len(link_patterns)}")
    print("="*60)
    print("\nTest data generation complete!")
    print(f"Database: {db_path}")


if __name__ == "__main__":
    main()
