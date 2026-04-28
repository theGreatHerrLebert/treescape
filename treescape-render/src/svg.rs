//! Deterministic SVG writer.
//!
//! Determinism rules pinned by the EVIDENT claim
//! `treescape-svg-determinism`:
//!
//! * Attributes within a tag are emitted in alphabetical order.
//! * Floats use a fixed `{:.4}` format. No locale-dependent formatting.
//! * No timestamps, generator comments, or random ids.
//! * Items are emitted in scene-graph insertion order — never via
//!   `HashMap` iteration.

use std::fmt::Write as _;

use treescape_core::layout::scene::{Color, Scene, SceneItem, TextAnchor};

/// SVG version bundled with the renderer. Embedded in the root tag so
/// downstream tooling can pin against it without parsing the body.
pub const SVG_VERSION: &str = "1.1";

/// Font family used for tip labels. v0.1 ships DejaVu Sans bundled
/// inside `src/fonts/DejaVuSans.ttf` and references it by family name
/// in the SVG so consumers fall back gracefully if the system font is
/// unavailable.
pub const FONT_FAMILY: &str = "DejaVu Sans, sans-serif";

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SvgError {
    Format(String),
}

impl std::fmt::Display for SvgError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Format(s) => write!(f, "svg format error: {}", s),
        }
    }
}

impl std::error::Error for SvgError {}

pub fn render_svg(scene: &Scene) -> Result<String, SvgError> {
    let mut out = String::new();
    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n");
    writeln!(
        &mut out,
        "<svg height=\"{h}\" version=\"{v}\" viewBox=\"0 0 {w} {h}\" width=\"{w}\" xmlns=\"http://www.w3.org/2000/svg\">",
        w = fmt_f(scene.canvas.width),
        h = fmt_f(scene.canvas.height),
        v = SVG_VERSION,
    )
    .map_err(|e| SvgError::Format(e.to_string()))?;

    for item in &scene.items {
        match item {
            SceneItem::Line {
                x1,
                y1,
                x2,
                y2,
                stroke,
                stroke_width,
            } => {
                writeln!(
                    &mut out,
                    "  <line stroke=\"{stroke}\" stroke-width=\"{sw}\" x1=\"{x1}\" x2=\"{x2}\" y1=\"{y1}\" y2=\"{y2}\"/>",
                    stroke = fmt_color(*stroke),
                    sw = fmt_f(*stroke_width),
                    x1 = fmt_f(*x1),
                    x2 = fmt_f(*x2),
                    y1 = fmt_f(*y1),
                    y2 = fmt_f(*y2),
                )
                .map_err(|e| SvgError::Format(e.to_string()))?;
            }
            SceneItem::Text {
                x,
                y,
                text,
                font_size,
                color,
                anchor,
                is_tip_label: _,
            } => {
                writeln!(
                    &mut out,
                    "  <text fill=\"{fill}\" font-family=\"{family}\" font-size=\"{size}\" text-anchor=\"{anchor}\" x=\"{x}\" y=\"{y}\">{escaped}</text>",
                    fill = fmt_color(*color),
                    family = FONT_FAMILY,
                    size = fmt_f(*font_size),
                    anchor = fmt_anchor(*anchor),
                    x = fmt_f(*x),
                    y = fmt_f(*y),
                    escaped = xml_escape(text),
                )
                .map_err(|e| SvgError::Format(e.to_string()))?;
            }
        }
    }

    out.push_str("</svg>\n");
    Ok(out)
}

fn fmt_f(v: f64) -> String {
    let s = format!("{:.4}", v);
    // Trim trailing zeros and a trailing decimal point so "1.0000" -> "1",
    // "1.5000" -> "1.5". Keep "-0" -> "0" via parsing.
    let trimmed = if s.contains('.') {
        let t = s.trim_end_matches('0').trim_end_matches('.');
        if t.is_empty() || t == "-" {
            "0".to_string()
        } else {
            t.to_string()
        }
    } else {
        s
    };
    if trimmed == "-0" {
        "0".to_string()
    } else {
        trimmed
    }
}

fn fmt_color(c: Color) -> String {
    if c.a == 255 {
        format!("#{:02x}{:02x}{:02x}", c.r, c.g, c.b)
    } else {
        format!(
            "rgba({},{},{},{:.3})",
            c.r,
            c.g,
            c.b,
            c.a as f64 / 255.0
        )
    }
}

fn fmt_anchor(a: TextAnchor) -> &'static str {
    match a {
        TextAnchor::Start => "start",
        TextAnchor::Middle => "middle",
        TextAnchor::End => "end",
    }
}

fn xml_escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&apos;"),
            c => out.push(c),
        }
    }
    out
}

/// The bundled DejaVu Sans font, embedded at compile time. Provided
/// for downstream measurement tools (e.g. fontdue) that want to size
/// labels exactly. Not directly written into the SVG: the SVG
/// references the font by family name and the consumer's renderer
/// fetches glyphs.
pub const DEJAVU_SANS_TTF: &[u8] =
    include_bytes!("fonts/DejaVuSans.ttf");

#[cfg(test)]
mod tests {
    use super::*;
    use treescape_core::layout::rectangular::{
        build_rectangular_scene, rectangular_layout, SceneOptions,
    };
    use treescape_core::newick::parse;

    #[test]
    fn fmt_f_trims_zeros() {
        assert_eq!(fmt_f(1.0), "1");
        assert_eq!(fmt_f(1.5), "1.5");
        assert_eq!(fmt_f(0.0), "0");
        assert_eq!(fmt_f(-0.0), "0");
        assert_eq!(fmt_f(-1.5), "-1.5");
        assert_eq!(fmt_f(0.12345), "0.1235");
    }

    #[test]
    fn fmt_color_short_form_for_opaque() {
        assert_eq!(fmt_color(Color::black()), "#000000");
        assert_eq!(fmt_color(Color::rgb(255, 0, 0)), "#ff0000");
        assert!(fmt_color(Color::rgba(0, 0, 0, 128)).starts_with("rgba("));
    }

    #[test]
    fn xml_escape_handles_special_chars() {
        assert_eq!(xml_escape("a<b>c&d\"e'f"), "a&lt;b&gt;c&amp;d&quot;e&apos;f");
    }

    #[test]
    fn render_balanced_4_smoke() {
        let t = parse("((a:1.0,b:1.0):1.0,(c:1.0,d:1.0):1.0);").unwrap();
        let l = rectangular_layout(&t);
        let s = build_rectangular_scene(&t, &l, &SceneOptions::default());
        let svg = render_svg(&s).unwrap();
        assert!(svg.starts_with("<?xml"));
        assert!(svg.contains("<svg"));
        assert!(svg.contains("<line"));
        assert!(svg.contains("<text"));
        for tip in ["a", "b", "c", "d"] {
            assert!(
                svg.contains(&format!(">{}</text>", tip)),
                "missing tip {tip}"
            );
        }
        assert!(svg.ends_with("</svg>\n"));
    }

    #[test]
    fn render_is_byte_deterministic() {
        let t = parse("((a:1.0,b:1.0):1.0,(c:1.0,d:1.0):1.0);").unwrap();
        let l = rectangular_layout(&t);
        let s1 = build_rectangular_scene(&t, &l, &SceneOptions::default());
        let s2 = build_rectangular_scene(&t, &l, &SceneOptions::default());
        let svg1 = render_svg(&s1).unwrap();
        let svg2 = render_svg(&s2).unwrap();
        assert_eq!(svg1, svg2);
    }

    #[test]
    fn render_attributes_alphabetical() {
        // Quick check on a known fragment: <line stroke=... stroke-width=... x1=... x2=... y1=... y2=.../>
        let t = parse("(a:1.0,b:1.0);").unwrap();
        let svg = crate::render_rectangular(&t, &SceneOptions::default()).unwrap();
        let line_idx = svg.find("<line ").unwrap();
        let line_end = svg[line_idx..].find("/>").unwrap();
        let line = &svg[line_idx..line_idx + line_end];
        // Expected attribute order: stroke, stroke-width, x1, x2, y1, y2
        let attrs = ["stroke=", "stroke-width=", "x1=", "x2=", "y1=", "y2="];
        let mut last = 0;
        for a in attrs {
            let pos = line.find(a).unwrap_or_else(|| {
                panic!("missing attribute {a} in line: {line}");
            });
            assert!(pos > last, "attribute {a} out of order in line: {line}");
            last = pos;
        }
    }

    #[test]
    fn dejavu_font_bundled() {
        // ~700KB; verify via a minimum size and the TTF magic bytes.
        assert!(DEJAVU_SANS_TTF.len() > 100_000);
        assert_eq!(&DEJAVU_SANS_TTF[..4], &[0x00, 0x01, 0x00, 0x00]);
    }
}
