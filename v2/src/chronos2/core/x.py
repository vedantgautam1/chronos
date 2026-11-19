"""B03 step 0 proof (b): a file this build widened its OWN spec to allow.

The guards read touches from the spec at the BASE commit, so widening the spec
on the branch changes nothing: scope must still charge this path.
"""
