# REF: the mutation tables of tools/mutate_aruco_ids.py and mutate_aruco_label.py at c8216ff
# (rows on a core file only). Data; tests/core/test_ref_mutations.py runs them. Do not edit by hand.
MUTATIONS = [
 {
  "id": "M1",
  "tool": "tools/mutate_aruco_ids.py",
  "rule": "a deleted copy's id is handed out again (lowest FREE block, not never-printed)",
  "file": "CADExporter/bam_cad_core/aruco_numbering.py",
  "old": "start = next((s for s in starts if free(s, r) and unused(s, r)), None)",
  "new": "start = next((s for s in starts if free(s, r)), None)",
  "suites": [
   "tests/test_aruco_ids_stability.py"
  ],
  "must": "2a the new copy does not get the deleted copy's id"
 },
 {
  "id": "M2",
  "tool": "tools/mutate_aruco_ids.py",
  "rule": "the ledger is ignored (a copy does not get its own id back)",
  "file": "CADExporter/bam_cad_core/aruco_numbering.py",
  "old": "if e is not None and e.id is not None and free(e.id, r) and unused(e.id, r):",
  "new": "if False:",
  "suites": [
   "tests/test_aruco_ids_stability.py"
  ],
  "must": "24 every copy keeps the id it prints (Tag:1 stays 5, now through a part)"
 },
 {
  "id": "M3",
  "tool": "tools/mutate_aruco_ids.py",
  "rule": "no stamp match (pass 1 off)",
  "file": "CADExporter/bam_cad_core/aruco_numbering.py",
  "old": "(lambda e, r: bool(r.uid) and e.uid == r.uid, rank),",
  "new": "(lambda e, r: False, rank),",
  "suites": [
   "tests/test_aruco_ids_stability.py"
  ],
  "must": "23 moved + renamed: nothing renumbered"
 },
 {
  "id": "M4",
  "tool": "tools/mutate_aruco_ids.py",
  "rule": "no place match (pass 3 off)",
  "file": "CADExporter/bam_cad_core/aruco_numbering.py",
  "old": "(lambda e, r: near(e, r) and e.count == r.count, lambda i, r: (dist(ents[i], r),) + rank(i, r)),",
  "new": "(lambda e, r: False, rank),",
  "suites": [
   "tests/test_aruco_ids_stability.py"
  ],
  "must": "5 renamed, unstamped: nothing renumbered"
 },
 {
  "id": "M5",
  "tool": "tools/mutate_aruco_ids.py",
  "rule": "a stamped entry found again by its old PATH (a new copy given a freed name)",
  "file": "CADExporter/bam_cad_core/aruco_numbering.py",
  "old": "(lambda e, r: e.name == r.name and not e.uid, rank),",
  "new": "(lambda e, r: e.name == r.name, rank),",
  "suites": [
   "tests/test_aruco_ids_stability.py"
  ],
  "must": "8 the new 'Tag:2' does not inherit the deleted Tag:2's id"
 },
 {
  "id": "M6",
  "tool": "tools/mutate_aruco_ids.py",
  "rule": "the geometry's id taken although another copy printed it",
  "file": "CADExporter/bam_cad_core/aruco_numbering.py",
  "old": "if r.name not in done and free(r.base, r) and unused(r.base, r):",
  "new": "if r.name not in done and free(r.base, r):",
  "suites": [
   "tests/test_aruco_ids_stability.py"
  ],
  "must": "2d the first copy (the one printing its own 0) deleted: a new copy does not print 0"
 },
 {
  "id": "M7",
  "tool": "tools/mutate_aruco_ids.py",
  "rule": "an override written over the copy's auto id (clearing it does not go back)",
  "file": "CADExporter/bam_cad_core/aruco_numbering.py",
  "old": "auto_id = int(r.final) if r.source in (\"auto\", \"model\", \"fixed\") else None",
  "new": "auto_id = int(r.final)",
  "suites": [
   "tests/test_aruco_ids_stability.py"
  ],
  "must": "13c override cleared: Tag:4 is back on its own auto id"
 },
 {
  "id": "M8",
  "tool": "tools/mutate_aruco_ids.py",
  "rule": "a full dictionary reuses the NEWEST retired id",
  "file": "CADExporter/bam_cad_core/aruco_numbering.py",
  "old": "max(printed.get(s + k, (-1, \"\"))[0] for k in range(r.count)), s))",
  "new": "-max(printed.get(s + k, (-1, \"\"))[0] for k in range(r.count)), s))",
  "suites": [
   "tests/test_aruco_ids_stability.py"
  ],
  "must": "14a the first new copy reuses the id retired the LONGEST ago (10)"
 },
 {
  "id": "M9",
  "tool": "tools/mutate_aruco_ids.py",
  "rule": "a hidden copy's id is not reserved (treated as retired)",
  "file": "CADExporter/bam_cad_core/aruco_numbering.py",
  "old": "if e is not None and (r.hidden or r.override is not None or r.error):",
  "new": "if e is not None and (r.override is not None or r.error):",
  "suites": [
   "tests/test_aruco_ids_stability.py"
  ],
  "must": "14a the first new copy reuses the id retired the LONGEST ago (10)"
 },
 {
  "id": "M10",
  "tool": "tools/mutate_aruco_ids.py",
  "rule": "printed ids are not recorded",
  "file": "CADExporter/bam_cad_core/aruco_numbering.py",
  "old": "new.mark_printed(r.family, r.ids, s, r.name)",
  "new": "pass",
  "suites": [
   "tests/test_aruco_ids_stability.py"
  ],
  "must": "2a the new copy does not get the deleted copy's id"
 },
 {
  "id": "M11",
  "tool": "tools/mutate_aruco_ids.py",
  "rule": "an old node's state is not seeded into the ledger",
  "file": "CADExporter/bam_cad_core/aruco_numbering.py",
  "old": "if (ledger is None or not ledger.entries) and (state or {}).get(\"final\"):",
  "new": "if False:",
  "suites": [
   "tests/test_aruco_ids_stability.py"
  ],
  "must": "19b ... and the copy deleted before the switch keeps its id retired"
 },
 {
  "id": "M12",
  "tool": "tools/mutate_aruco_ids.py",
  "rule": "the stamps' birth order ignored (natural path order only)",
  "file": "CADExporter/bam_cad_core/aruco_numbering.py",
  "old": "order = sorted(auto, key=lambda r: (born.get(r.path) is None, born.get(r.path) or 0.0,",
  "new": "order = sorted(auto, key=lambda r: (0, 0.0,",
  "suites": [
   "tests/test_aruco_ids_stability.py"
  ],
  "must": "12a nothing deleted since: the stamps' birth order gives every id back"
 },
 {
  "id": "M13",
  "tool": "tools/mutate_aruco_ids.py",
  "rule": "a pasted copy keeps its original's stamp",
  "file": "CADExporter/bam_cad_core/aruco_numbering.py",
  "old": "out |= set(keys) - {win}",
  "new": "pass",
  "suites": [
   "tests/test_aruco_ids_stability.py"
  ],
  "must": "15d ... and a stamp of its own (the next OK finds both by stamp)"
 },
 {
  "id": "M14",
  "tool": "tools/mutate_aruco_ids.py",
  "rule": "one ledger entry matched by two copies",
  "file": "CADExporter/bam_cad_core/aruco_numbering.py",
  "old": "left.discard(i)",
  "new": "pass",
  "suites": [
   "tests/test_aruco_ids_stability.py"
  ],
  "must": "15e two rows with one uid: the entry is taken once (by the copy at its path)"
 },
 {
  "id": "M15",
  "tool": "tools/mutate_aruco_ids.py",
  "rule": "'the same place' 1000 x too loose (0.5 m)",
  "file": "CADExporter/bam_cad_core/aruco_numbering.py",
  "old": "PLACE_TOL_M = 0.0005",
  "new": "PLACE_TOL_M = 0.5",
  "suites": [
   "tests/test_aruco_ids_stability.py"
  ],
  "must": "2e a new copy 2 mm from a deleted one's place is a NEW copy (0.5 mm is 'put back')"
 },
 {
  "id": "M16",
  "tool": "tools/mutate_aruco_ids.py",
  "rule": "a hidden copy forgets its entry (it is marked gone)",
  "file": "CADExporter/bam_cad_core/aruco_numbering.py",
  "old": "e.uid, e.name, e.at, e.state, e.seen = uid, r.name, r.at, \"hidden\", s",
  "new": "e.uid, e.name, e.at, e.state, e.seen = uid, r.name, r.at, \"gone\", s",
  "suites": [
   "tests/test_aruco_ids_stability.py"
  ],
  "must": "9c while hidden the ledger holds its id for it (not retired)"
 },
 {
  "id": "M17",
  "tool": "tools/mutate_aruco_ids.py",
  "rule": "a reused id stays with the hidden / deleted copy that had it",
  "file": "CADExporter/bam_cad_core/aruco_numbering.py",
  "old": "e.id = None                # its id went to another copy (a full dictionary)",
  "new": "pass",
  "suites": [
   "tests/test_aruco_ids_stability.py"
  ],
  "must": "14c' ... and the hidden copy's ledger entry gives that id up"
 },
 {
  "id": "L1",
  "tool": "tools/mutate_aruco_label.py",
  "rule": "a refused label gets no preview (nothing to see)",
  "file": "CADExporter/bam_cad_core/aruco_label.py",
  "old": "        if pv.parts:\n            lab.preview = pv",
  "new": "        if False:\n            lab.preview = pv",
  "suites": [
   "tests/test_aruco_label_preview.py"
  ],
  "must": "P1b but a preview"
 },
 {
  "id": "L2",
  "tool": "tools/mutate_aruco_label.py",
  "rule": "Build anyway is ignored (never built)",
  "file": "CADExporter/bam_cad_core/aruco_label.py",
  "old": "        if s.build_anyway:",
  "new": "        if False:",
  "suites": [
   "tests/test_aruco_label_preview.py"
  ],
  "must": "P2 Build anyway"
 },
 {
  "id": "L3",
  "tool": "tools/mutate_aruco_label.py",
  "rule": "the clear zone is not reported",
  "file": "CADExporter/bam_cad_core/aruco_label.py",
  "old": "        if d > tol:\n            out.append(f\"inside the detector's clear zone",
  "new": "        if False:\n            out.append(f\"inside the detector's clear zone",
  "suites": [
   "tests/test_aruco_label_preview.py"
  ],
  "must": "P8b"
 },
 {
  "id": "L4",
  "tool": "tools/mutate_aruco_label.py",
  "rule": "off the face is not reported",
  "file": "CADExporter/bam_cad_core/aruco_label.py",
  "old": "            if hangs or any(_in_rect(r, v) for v in outer):",
  "new": "            if False:",
  "suites": [
   "tests/test_aruco_label_preview.py"
  ],
  "must": "P1d"
 },
 {
  "id": "L5",
  "tool": "tools/mutate_aruco_label.py",
  "rule": "letters too small for the nozzle are not reported",
  "file": "CADExporter/bam_cad_core/aruco_label.py",
  "old": "    if low < need - TOL:",
  "new": "    if False:",
  "suites": [
   "tests/test_aruco_label_preview.py"
  ],
  "must": "P5 typed 2.0 mm letters"
 },
 {
  "id": "L6",
  "tool": "tools/mutate_aruco_label.py",
  "rule": "the preview is not at the smallest printable cap",
  "file": "CADExporter/bam_cad_core/aruco_label.py",
  "old": "    cap = float(s.cap_mm) if s.cap_mm > 0 else min_cap(s.nozzle_mm, s.stroke_mm)",
  "new": "    cap = float(s.cap_mm) if s.cap_mm > 0 else 2.0 * min_cap(s.nozzle_mm, s.stroke_mm)",
  "suites": [
   "tests/test_aruco_label_preview.py"
  ],
  "must": "P1b but a preview"
 },
 {
  "id": "L7",
  "tool": "tools/mutate_aruco_label.py",
  "rule": "a refused nudge is drawn where it was placed, not where it was nudged",
  "file": "CADExporter/bam_cad_core/aruco_label.py",
  "old": "            Box(b.cx + dx, b.cy + dy, b.length, b.width, b.angle) for b in p.boxes]))",
  "new": "            Box(b.cx, b.cy, b.length, b.width, b.angle) for b in p.boxes]))",
  "suites": [
   "tests/test_aruco_label_preview.py"
  ],
  "must": "P8 nudge"
 },
 {
  "id": "L8",
  "tool": "tools/mutate_aruco_label.py",
  "rule": "a refused nudge is built at the automatic spot again (silently)",
  "file": "CADExporter/bam_cad_core/aruco_label.py",
  "old": "            lab = Label(settings=s, preview=pv)",
  "new": "            pass",
  "suites": [
   "tests/test_aruco_label_preview.py"
  ],
  "must": "P8 nudge"
 },
 {
  "id": "L9",
  "tool": "tools/mutate_aruco_label.py",
  "rule": "a copy of a label built anyway is not laid out as it was",
  "file": "CADExporter/bam_cad_core/aruco_label.py",
  "old": "    if lab.forced:",
  "new": "    if False:",
  "suites": [
   "tests/test_aruco_label_preview.py"
  ],
  "must": "P13 a copy of a label built anyway"
 },
 {
  "id": "L10",
  "tool": "tools/mutate_aruco_label.py",
  "rule": "over a hole is not reported",
  "file": "CADExporter/bam_cad_core/aruco_label.py",
  "old": "            out.append(\"over a hole in the face\")",
  "new": "            pass",
  "suites": [
   "tests/test_aruco_label_preview.py"
  ],
  "must": "P8 nudge (+18, +0)"
 },
 {
  "id": "L11",
  "tool": "tools/mutate_aruco_label.py",
  "rule": "a text in the corner cells is called merely 'too close'",
  "file": "CADExporter/bam_cad_core/aruco_label.py",
  "old": "                if into > TOL:",
  "new": "                if False:",
  "suites": [
   "tests/test_aruco_label_preview.py"
  ],
  "must": "P10 on the black"
 },
 {
  "id": "L12",
  "tool": "tools/mutate_aruco_label.py",
  "rule": "the record drops the preview",
  "file": "CADExporter/bam_cad_core/aruco_label.py",
  "old": "                d[\"preview\"] = self.preview.to_dict(nd)",
  "new": "                pass",
  "suites": [
   "tests/test_aruco_label_preview.py"
  ],
  "must": "P12 the record keeps the preview"
 },
 {
  "id": "L13",
  "tool": "tools/mutate_aruco_label.py",
  "rule": "a label with violations counts as ok",
  "file": "CADExporter/bam_cad_core/aruco_label.py",
  "old": "                and not self.violations)",
  "new": "                )",
  "suites": [
   "tests/test_aruco_label_preview.py"
  ],
  "must": "P2 Build anyway"
 },
 {
  "id": "L14",
  "tool": "tools/mutate_aruco_label.py",
  "rule": "copies of a refused label do not say why",
  "file": "CADExporter/bam_cad_core/aruco_label.py",
  "old": "        if lab is not None and lab.settings.on and lab.preview is not None:",
  "new": "        if False:",
  "suites": [
   "tests/test_aruco_label_preview.py"
  ],
  "must": "P14 copies are never silent"
 },
 {
  "id": "L15",
  "tool": "tools/mutate_aruco_label.py",
  "rule": "an older record (no 'rule') is laid out under the new rule: it moves",
  "file": "CADExporter/bam_cad_core/aruco_label.py",
  "old": "            rv = int(d.get(\"rule\", 1))",
  "new": "            rv = int(d.get(\"rule\", 2))",
  "suites": [
   "tests/test_aruco_label_rule1.py"
  ],
  "must": "rule 1, "
 }
]
