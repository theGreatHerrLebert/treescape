# Unit tests for Treescape.jl. Cross-language byte parity lives in
# tests/oracle/test_julia_parity.py (driving parity_runner.jl) and the
# no-abort property in tests/oracle/test_jl_ffi_no_abort.py.

using Test
using Treescape

const NEWICK = "((a:0.1,b:0.2)95:0.3,(c:0.15,(d:0.05,e:0.07)70:0.1)88:0.2);"
# A callable struct (not a Function) used as a colormap.
struct RedMap end
(::RedMap)(t) = "#ff0000"

const META = (tip=["a", "b", "c", "d", "e"], grp=["x", "x", "y", "y", "z"], w=[0.1, 0.9, 0.4, 0.4, 0.7])

@testset "Treescape.jl" begin
    @testset "pyfloat matches Python str(float(x))" begin
        # Expected strings generated with CPython 3.12.
        for (x, expected) in [
            (0.05, "0.05"),
            (1.0, "1.0"),
            (1e-05, "1e-05"),
            (1e+16, "1e+16"),
            (1000000000000000.0, "1000000000000000.0"),
            (0.0001, "0.0001"),
            (123456.789, "123456.789"),
            (1.5e-07, "1.5e-07"),
            (-2.5, "-2.5"),
            (-0.0, "-0.0"),
            (0.0, "0.0"),
            (1e+22, "1e+22"),
            (1 / 3, "0.3333333333333333"),
            (9007199254740992, "9007199254740992.0"),
            (5e-324, "5e-324"),
            (1.7976931348623157e+308, "1.7976931348623157e+308"),
            (0.1 + 0.2, "0.30000000000000004"),
            (100.0, "100.0"),
            (1234567890123456.0, "1234567890123456.0"),
            (1.2345678901234568e+16, "1.2345678901234568e+16"),
        ]
            @test Treescape.pyfloat(x) == expected
        end
    end

    @testset "colors" begin
        @test Treescape.parse_color("#ff8000") == (0xff, 0x80, 0x00, 0xff)
        @test Treescape.parse_color("##ff800080") == (0xff, 0x80, 0x00, 0x80)
        @test Treescape.parse_color((1.9, 2, 3)) == (0x01, 0x02, 0x03, 0xff)
        @test Treescape.parse_color((1, 2, 3, 4)) == (0x01, 0x02, 0x03, 0x04)
        @test_throws ArgumentError Treescape.parse_color("#fff")
        @test_throws ArgumentError Treescape.parse_color("#gg0000")
        @test_throws ArgumentError Treescape.parse_color(42)
    end

    @testset "source heuristic and errors" begin
        @test TreePlot(NEWICK).tree.tip_order == ["a", "b", "c", "d", "e"]
        path = tempname() * ".nwk"
        write(path, NEWICK)
        @test TreePlot(path).tree.tip_order == ["a", "b", "c", "d", "e"]
        @test_throws Treescape.TreescapeError TreePlot("(a,b")
        @test_throws Treescape.TreescapeError TreePlot("a];")
        @test_throws ArgumentError layout!(TreePlot(NEWICK), :radial)
    end

    @testset "rendering" begin
        p = TreePlot(NEWICK)
        svg = to_svg(p)
        @test occursin("<svg", svg)
        @test to_svg(p) == svg                          # deterministic
        @test sprint(show, MIME("image/svg+xml"), p) == svg
        layout!(p, "circular")
        @test to_svg(p) != svg
        out = tempname() * ".svg"
        @test save(p, out) === p
        @test read(out, String) == to_svg(p)
    end

    @testset "options! keeps earlier values" begin
        p = TreePlot(NEWICK)
        options!(p; label_offset=12, stroke_width=2)
        options!(p; font_size=18)
        @test p.scene_opts.label_offset == 12.0
        @test p.scene_opts.font_size == 18.0
        @test p.circular_opts.stroke_width == 2.0
        options!(p; px_per_x=250)
        @test p.circular_opts.px_per_r == 250.0
    end

    @testset "metadata styling" begin
        p = join_metadata!(TreePlot(NEWICK), META; on=:tip)
        @test_throws ArgumentError join_metadata!(p, META; on=:tip)             # collision
        @test_throws ArgumentError join_metadata!(TreePlot(NEWICK), (tip=["a", "a"], v=[1, 2]); on="tip")
        @test_throws ArgumentError join_metadata!(TreePlot(NEWICK), (tip=["zz"], v=[1]); on="tip")
        @test_throws ArgumentError color_tips_by!(p, :missing_column)

        # A callable cmap sees the same t as the built-in viridis.
        a = color_tips_by!(join_metadata!(TreePlot(NEWICK), META; on=:tip), :w)
        b = color_tips_by!(join_metadata!(TreePlot(NEWICK), META; on=:tip), :w; cmap=t -> Treescape.viridis(t))
        @test to_svg(a) == to_svg(b)

        # Non-monophyletic branches warn, like TreescapeStyleWarning.
        q = join_metadata!(TreePlot(NEWICK), META; on=:tip)
        @test_logs (:warn, r"not monophyletic for metadata column 'grp'") match_mode = :any color_branches_by!(q, :grp)

        # A failed call leaves prior branch styling intact.
        before = to_svg(q)
        @test_throws ArgumentError color_branches_by!(q, :grp; palette=Dict("x" => "#000000"))
        @test to_svg(q) == before

        @test_throws ArgumentError width_branches_by!(q, :grp)                  # non-numeric
        @test_throws ArgumentError width_branches_by!(q, :w; wmin=-1)
        width_branches_by!(q, :w; wmin=0.5, wmax=6)
        @test !isempty(q.branch_widths)
    end

    @testset "review round 1 regressions" begin
        # -0.0 and 0.0 are one category, as in Python.
        cat = (tip=["a", "b", "c", "d", "e"], z=Any[-0.0, 0.0, "x", "x", "x"])
        p = join_metadata!(TreePlot(NEWICK), cat; on=:tip)
        color_tips_by!(p, :z)
        @test p.tip_colors["a"] == p.tip_colors["b"]
        @test_logs color_branches_by!(join_metadata!(TreePlot(NEWICK), cat; on=:tip), :z; palette=Dict(0.0 => "#111111", "x" => "#222222"))

        # Callable structs are colormaps too.
        q = color_tips_by!(join_metadata!(TreePlot(NEWICK), META; on=:tip), :w; cmap=RedMap())
        @test all(==((0xff, 0x00, 0x00, 0xff)), values(q.tip_colors))

        # deepcopy shares the tree owner instead of duplicating the handle.
        orig = TreePlot(NEWICK)
        dup = deepcopy(orig)
        @test dup.tree === orig.tree
        orig = nothing
        GC.gc(); GC.gc()
        @test occursin("<svg", to_svg(dup))

        # Non-finite geometry is an error, not NaN in the SVG.
        @test_throws Treescape.TreescapeError to_svg(options!(TreePlot(NEWICK); padding=NaN))
        @test_throws Treescape.TreescapeError to_svg(options!(TreePlot(NEWICK); font_size=1e300))

        # XML-forbidden characters in names are replaced, not emitted raw.
        @test !occursin('\x01', to_svg(TreePlot("('a\x01b':1,c:1);")))

        # Huge finite alpha clamps to opaque; non-finite alpha is an error.
        r = highlight_clade!(TreePlot(NEWICK), ["a", "b"]; alpha=1e20)
        @test r.highlights[1][2][4] == 0xff
        @test_throws ArgumentError highlight_clade!(TreePlot(NEWICK), ["a"]; alpha=Inf)
    end

    @testset "annotations" begin
        p = scale_bar!(TreePlot(NEWICK), 1e-5)
        @test p.scale_bar == (1e-5, "1e-05")
        @test_throws ArgumentError scale_bar!(p, 0)
        support_labels!(p; min_value=80)
        @test p.support_min == 80.0
        @test occursin("95", to_svg(p))
        @test !occursin(">70<", to_svg(p))
    end
end
