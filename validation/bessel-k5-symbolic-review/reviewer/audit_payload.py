#!/usr/bin/env python3
"""Check the finite K5 export against both immutable certified moment balls."""
import hashlib
import json
from pathlib import Path

import audit

audit.ctx.dps = 20350
directory = audit.BESSEL / 'upstream-moment-bindings'
payload = directory / 'constants.json'
raw = payload.read_bytes()
data = json.loads(raw)
moments = ['B1', 'J1', 'B3', 'J3']
identities = {
    'vakint::K5Moment(1)': 'B1', 'vakint::K5LogMoment(1)': 'J1',
    'vakint::K5Moment(3)': 'B3', 'vakint::K5LogMoment(3)': 'J3',
}
profiles = {
    label: json.loads((audit.BESSEL / f'high-guard/profile-{label}.json').read_bytes())
    for label in ('a', 'b')
}
audit.require(len(data['constants']) == 4, 'Expected exactly four finite moments')
audit.require({row['symbol'] for row in data['constants']} == set(identities), 'Moment identity mismatch')
checks = []
for row in data['constants']:
    moment = identities[row['symbol']]
    index = moments.index(moment)
    audit.require(row['significant_digits'] == 20000 and row['stored_significant_digits'] == 20008
                  and row['error_quality'] == 'Bounded', 'Capability drift')
    for label, profile in profiles.items():
        value = audit.arb(profile['values'][index])
        audit.require(audit.rounding_cell(value, 20008) == row['value'], 'Incorrect stored moment rounding')
        error = abs(value - audit.arb(row['value'])).upper()
        declared = audit.arb(row['absolute_error'])
        audit.require(error <= declared.lower(), 'Published bound fails to contain full source ball')
        audit.require(error < (abs(value).lower() * audit.arb(10)**(-20000)).lower(),
                      '20k significant precision not established')
        checks.append({
            'symbol': row['symbol'], 'sealed_moment': moment, 'profile': label,
            'stored_rounding_unique': True,
            'published_absolute_error_contains_full_source_ball': True,
            'validated_significant_digits': 20000,
        })
report = {
    'schema': 'vakint.independent-K5-export-audit.v1', 'accepted': True,
    'payload_sha256': hashlib.sha256(raw).hexdigest(),
    'export_validation_sha256': hashlib.sha256((directory / 'validation.json').read_bytes()).hexdigest(),
    'audit_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'formula_audit_script_sha256': hashlib.sha256(Path(audit.__file__).read_bytes()).hexdigest(),
    'checks': checks, 'finite_source_cap': 20000, 'no_master_alias_inversion': True,
}
output = Path(__file__).parent / 'moment-payload-audit.json'
output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'accepted': True, 'report': str(output),
                  'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}))
