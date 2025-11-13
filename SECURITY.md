# Security model

Part of the motivation for having hash collection infrastructure is that you
should not need to trust any single party. This means `lila` should not be such
a single trusted party either.

The attestations collected by `lila` each have their own signature, provided by
its respective builder. High-security clients are encouraged to decide for
themselves which builders to trust, and to check their signatures. This way
little trust needs to be placed in `lila` itself: at worst we could 'lie by
omission' and obscure some attestations.

## Availability

`lila` itself is built for flexible collection and reporting on attestations,
and not particularly optimized for DoS protection.

## Data providers

Inserting data into `lila` is protected by authentication tokens. In principle
we trust builders not to provide malicious content; for example, we do not
consider it a security issue that a malicious report could trigger XSS or DoS
situations. This is acceptable because ultimately the trust is not in
`lila`, but in the signatures on the attestations. In case of abuse we can
identify the abuser, remove their access and clean up their inputs.

# Reporting security issues

If you find a security issue, please report it in private email to
arnout@bzzt.net and/or lila@malka.sh .
