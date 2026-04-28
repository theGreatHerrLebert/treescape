//! Scene graph types — the geometric primitives that sit between
//! [`crate::layout`] (which thinks in tree coordinates) and
//! [`treescape_render`] (which thinks in pixels and SVG bytes).
//!
//! Designed to be deterministic: items are stored in a [`Vec`] and
//! emitted in insertion order; no `HashMap` iteration leaks into
//! downstream renderers.

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct Color {
    pub r: u8,
    pub g: u8,
    pub b: u8,
    pub a: u8,
}

impl Color {
    pub const fn rgb(r: u8, g: u8, b: u8) -> Self {
        Self { r, g, b, a: 255 }
    }

    pub const fn black() -> Self {
        Self::rgb(0, 0, 0)
    }

    pub const fn rgba(r: u8, g: u8, b: u8, a: u8) -> Self {
        Self { r, g, b, a }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct Canvas {
    pub width: f64,
    pub height: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TextAnchor {
    Start,
    Middle,
    End,
}

#[derive(Debug, Clone)]
pub enum SceneItem {
    /// A filled rectangle. Used by Phase-3 clade highlighting; v0.2
    /// only ships fill (no stroke) but the field is here for forward
    /// compatibility. Emitted before lines so highlights render
    /// behind branches.
    Rect {
        x: f64,
        y: f64,
        width: f64,
        height: f64,
        fill: Color,
    },
    /// Filled annular sector for circular clade highlights (v0.3 Phase 3).
    /// Coordinates and radii are in pixels (post-projection), matching
    /// `Rect`. Emitted before `Line`/`Arc`/`Text` so highlights render
    /// behind branches and labels. See `docs/conventions.md` (v0.3,
    /// circular clade highlighting) for the geometry rules.
    AnnularSector {
        cx: f64,
        cy: f64,
        r_inner: f64,
        r_outer: f64,
        theta_min: f64,
        theta_max: f64,
        fill: Color,
    },
    Line {
        x1: f64,
        y1: f64,
        x2: f64,
        y2: f64,
        stroke: Color,
        stroke_width: f64,
    },
    /// A circular arc from `(x1, y1)` to `(x2, y2)` along a circle of
    /// the given `radius`. `large_arc` and `sweep_clockwise` map
    /// directly onto SVG path arc flags. Used by circular layouts to
    /// draw the spine connecting children of an internal node.
    Arc {
        x1: f64,
        y1: f64,
        x2: f64,
        y2: f64,
        radius: f64,
        large_arc: bool,
        sweep_clockwise: bool,
        stroke: Color,
        stroke_width: f64,
    },
    Text {
        x: f64,
        y: f64,
        text: String,
        font_size: f64,
        color: Color,
        anchor: TextAnchor,
        /// True when this glyph corresponds to a tip label. Used by
        /// the tip-count invariant claim runner.
        is_tip_label: bool,
        /// Rotation in degrees, applied around `(x, y)`. 0.0 means
        /// upright. Used by circular layouts to keep tip labels
        /// radial. Rotation is emitted as `transform="rotate(deg, x,
        /// y)"`; deterministic float formatting handles the
        /// byte-equality claim.
        rotation_deg: f64,
    },
}

#[derive(Debug, Clone)]
pub struct Scene {
    pub canvas: Canvas,
    pub items: Vec<SceneItem>,
}

impl Scene {
    pub fn count_tip_labels(&self) -> usize {
        self.items
            .iter()
            .filter(|i| {
                matches!(
                    i,
                    SceneItem::Text {
                        is_tip_label: true,
                        ..
                    }
                )
            })
            .count()
    }

    /// Returns true when every coordinate in every item lies within
    /// `[0, canvas.width] x [0, canvas.height]`. Used by the
    /// `treescape-tip-count-invariant` claim.
    pub fn coords_within_canvas(&self, eps: f64) -> bool {
        let w = self.canvas.width + eps;
        let h = self.canvas.height + eps;
        for item in &self.items {
            match item {
                SceneItem::Rect {
                    x,
                    y,
                    width,
                    height,
                    ..
                } => {
                    if *x < -eps || *x + *width > w {
                        return false;
                    }
                    if *y < -eps || *y + *height > h {
                        return false;
                    }
                }
                SceneItem::AnnularSector {
                    cx,
                    cy,
                    r_outer,
                    ..
                } => {
                    if *cx - *r_outer < -eps || *cx + *r_outer > w {
                        return false;
                    }
                    if *cy - *r_outer < -eps || *cy + *r_outer > h {
                        return false;
                    }
                }
                SceneItem::Line { x1, y1, x2, y2, .. } => {
                    for &c in &[*x1, *x2] {
                        if c < -eps || c > w {
                            return false;
                        }
                    }
                    for &c in &[*y1, *y2] {
                        if c < -eps || c > h {
                            return false;
                        }
                    }
                }
                SceneItem::Arc { x1, y1, x2, y2, .. } => {
                    for &c in &[*x1, *x2] {
                        if c < -eps || c > w {
                            return false;
                        }
                    }
                    for &c in &[*y1, *y2] {
                        if c < -eps || c > h {
                            return false;
                        }
                    }
                }
                SceneItem::Text { x, y, .. } => {
                    if *x < -eps || *x > w || *y < -eps || *y > h {
                        return false;
                    }
                }
            }
        }
        true
    }
}
