//! Tip-label width measurement via fontdue.
//!
//! Backs the `treescape-text-width-vs-fontdue` EVIDENT claim. The
//! Python reference in `treescape_reference.text` reads HMTX advance
//! widths directly via fontTools; this module is the Rust counterpart
//! using fontdue. Both load the same `DejaVuSans.ttf` shipped under
//! `src/fonts/`.
//!
//! Scope: Latin only, no shaping (no kerning, no ligatures). See
//! `docs/conventions.md` for the v0.2 convention statement.

use fontdue::{Font, FontSettings};
use std::sync::OnceLock;

use crate::svg::DEJAVU_SANS_TTF;

fn dejavu_sans() -> &'static Font {
    static FONT: OnceLock<Font> = OnceLock::new();
    FONT.get_or_init(|| {
        Font::from_bytes(DEJAVU_SANS_TTF, FontSettings::default())
            .expect("bundled DejaVuSans.ttf failed to parse via fontdue")
    })
}

/// Width in pixels of `text` rendered at `font_size`, measured as the
/// sum of fontdue advance widths for each character.
///
/// Empty strings return 0.0. Characters absent from the font fall back
/// to fontdue's missing-glyph metric (typically the `.notdef` glyph
/// advance, not zero) — that matches what an SVG renderer would do.
pub fn text_width(text: &str, font_size: f64) -> f64 {
    if text.is_empty() {
        return 0.0;
    }
    let font = dejavu_sans();
    text.chars()
        .map(|c| font.metrics(c, font_size as f32).advance_width as f64)
        .sum()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_string_is_zero() {
        assert_eq!(text_width("", 12.0), 0.0);
    }

    #[test]
    fn narrow_glyph_is_smaller_than_wide() {
        let i = text_width("i", 12.0);
        let w = text_width("W", 12.0);
        assert!(i > 0.0);
        assert!(w > i, "W ({}) should be wider than i ({})", w, i);
    }

    #[test]
    fn width_scales_linearly_with_font_size() {
        let small = text_width("Hello", 12.0);
        let large = text_width("Hello", 24.0);
        assert!(
            (large - 2.0 * small).abs() < 0.01,
            "{} vs 2 * {}",
            large,
            small
        );
    }

    #[test]
    fn multi_char_is_sum_of_chars() {
        let parts: f64 = "abc"
            .chars()
            .map(|c| text_width(&c.to_string(), 12.0))
            .sum();
        let whole = text_width("abc", 12.0);
        assert!((parts - whole).abs() < 1e-9);
    }
}
