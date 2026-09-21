# Build the Julia artifact tarballs and Artifacts.toml (docs/conventions.md,
# "Distribution"). Run by .github/workflows/release.yml (stage julia-libs):
#
#   julia workflow/installed/make_artifacts.jl <repo> <out dir> <base url> <triplet>=<library> ...
#
# For each platform triplet (x86_64-linux-gnu, aarch64-linux-gnu,
# aarch64-apple-darwin, x86_64-apple-darwin, x86_64-w64-mingw32) the library
# and both license files become one artifact; the tarball goes to <out dir>
# and is bound in <out dir>/Artifacts.toml, lazily, at <base url>/<tarball>.

using Pkg.Artifacts, Base.BinaryPlatforms, SHA

repo, out, base_url = ARGS[1:3]
mkpath(out)
toml = joinpath(out, "Artifacts.toml")
isfile(toml) && rm(toml)
version = match(r"^version = \"(.+)\"$"m, read(joinpath(repo, "packages", "Treescape.jl", "Project.toml"), String))[1]
licenses = [joinpath(repo, "LICENSE"), joinpath(repo, "treescape-render", "src", "fonts", "LICENSE.DejaVu.txt")]

for spec in ARGS[4:end]
    triplet, lib = split(spec, "="; limit = 2)
    hash = create_artifact() do dir
        cp(lib, joinpath(dir, basename(lib)))
        # The execute bit is lost when CI moves files between jobs, and on
        # Windows a DLL without it cannot be loaded (Tar keeps the mode).
        chmod(joinpath(dir, basename(lib)), 0o755)
        for l in licenses
            cp(l, joinpath(dir, basename(l)))
        end
    end
    tarball = joinpath(out, "libtreescape_jl_connector-v$version-$triplet.tar.gz")
    archive_artifact(hash, tarball)
    sha = bytes2hex(open(sha256, tarball))
    bind_artifact!(toml, "libtreescape_jl_connector", hash;
        platform = parse(Platform, triplet), lazy = true, force = true,
        download_info = [("$(rstrip(base_url, '/'))/$(basename(tarball))", sha)])
    println("$triplet: $(basename(tarball)) sha256=$sha tree=$(bytes2hex(hash.bytes))")
end
