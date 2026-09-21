# Installed-package check for Julia (claim
# treescape-installed-packages-reproduce-gallery).
#
#   julia workflow/installed/check_installed.jl <repo root> <report.json>
#
# Installs Treescape.jl into a fresh temporary environment, asserts the
# connector library comes from the release ARTIFACT (not a development
# build or an override), runs the parity cases, and compares every case
# that names a committed gallery file byte for byte.

using Pkg
repo, report = ARGS
env = mktempdir()
Pkg.activate(env)
Pkg.develop(path = joinpath(repo, "packages", "Treescape.jl"))
Pkg.add("TOML")
using Treescape, TOML

haskey(ENV, "TREESCAPE_JL_LIB") && error("TREESCAPE_JL_LIB is set; the check must use the artifact")
lib = Treescape.library_path()
occursin(joinpath("artifacts", ""), lib) || error("connector library not from an artifact: $lib")

out = mktempdir()
runner = joinpath(repo, "packages", "Treescape.jl", "test", "parity_runner.jl")
cases = joinpath(repo, "tests", "fixtures", "parity", "cases.toml")
run(`$(Base.julia_cmd()) --project=$env $runner $cases $repo $out`)

results = Dict{String,Bool}()
for case in TOML.parsefile(cases)["cases"]
    haskey(case, "expect_file") || continue
    got = read(joinpath(out, case["name"] * ".svg"), String)
    expected = read(joinpath(repo, case["expect_file"]), String)
    results[case["expect_file"]] = got == expected
    got == expected || replace(expected, "\r\n" => "\n") != got ||
        println("$(case["expect_file"]): differs in line endings only (is the checkout converting them? see .gitattributes)")
end
mismatches = sort([k for (k, ok) in results if !ok])
open(report, "w") do io
    TOML.print(io, Dict("claim" => "treescape-installed-packages-reproduce-gallery", "platform" => string(Sys.MACHINE),
        "julia" => string(VERSION), "library" => lib, "checked" => length(results), "mismatches" => mismatches))
end
println("checked $(length(results)) gallery files; mismatches: $mismatches")
isempty(mismatches) || exit(1)
