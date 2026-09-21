//! Orientation of the rectangular layout (docs/conventions.md,
//! "Orientation"). Port of `treescape_reference.orientation`.
//!
//! The `Right` scene is built as always; every other orientation is an
//! exact transform of it. With the `Right` canvas `W x H`:
//!
//! ```text
//! Left   (x, y) -> (W - x, y)   canvas W x H   anchors start <-> end
//! Down   (x, y) -> (y, x)       canvas H x W   anchors start <-> end, rotation - 90
//! Up     (x, y) -> (y, W - x)   canvas H x W   anchors unchanged,    rotation - 90
//! ```
//!
//! Text is never transposed (that would mirror the glyphs): only its
//! anchor point moves, and the anchor and rotation keep it readable.

use crate::layout::scene::{Canvas, Scene, SceneItem, TextAnchor};

/// The direction the tree grows, from the root towards the tips.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum Orientation {
    #[default]
    Right,
    Down,
    Left,
    Up,
}

/// Every orientation, in the documented order.
pub const ORIENTATIONS: [&str; 4] = ["right", "down", "left", "up"];

impl Orientation {
    /// Parse `"right" | "down" | "left" | "up"`; the error text matches
    /// the reference's `check_orientation`.
    pub fn parse(name: &str) -> Result<Self, String> {
        match name {
            "right" => Ok(Self::Right),
            "down" => Ok(Self::Down),
            "left" => Ok(Self::Left),
            "up" => Ok(Self::Up),
            other => Err(format!(
                "orientation must be one of ('right', 'down', 'left', 'up'), got {}",
                crate::seq_distance::repr(other)
            )),
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            Self::Right => "right",
            Self::Down => "down",
            Self::Left => "left",
            Self::Up => "up",
        }
    }
}

fn swap(anchor: TextAnchor) -> TextAnchor {
    match anchor {
        TextAnchor::Start => TextAnchor::End,
        TextAnchor::End => TextAnchor::Start,
        TextAnchor::Middle => TextAnchor::Middle,
    }
}

/// The `Right` scene transformed to `orientation`. Rectangular scenes
/// only: arcs and annular sectors (circular items) pass through
/// unchanged, and the hosts reject orientation for circular layouts.
pub fn orient_scene(scene: Scene, orientation: Orientation) -> Scene {
    if orientation == Orientation::Right {
        return scene;
    }
    let (w, h) = (scene.canvas.width, scene.canvas.height);
    let point = |x: f64, y: f64| -> (f64, f64) {
        match orientation {
            Orientation::Left => (w - x, y),
            Orientation::Down => (y, x),
            Orientation::Up => (y, w - x),
            Orientation::Right => (x, y),
        }
    };
    let canvas = match orientation {
        Orientation::Left | Orientation::Right => Canvas {
            width: w,
            height: h,
        },
        Orientation::Down | Orientation::Up => Canvas {
            width: h,
            height: w,
        },
    };
    let swap_anchor = matches!(orientation, Orientation::Left | Orientation::Down);
    let rotate = matches!(orientation, Orientation::Down | Orientation::Up);

    let items = scene
        .items
        .into_iter()
        .map(|item| match item {
            SceneItem::Rect {
                x,
                y,
                width,
                height,
                fill,
            } => match orientation {
                Orientation::Left => SceneItem::Rect {
                    x: w - x - width,
                    y,
                    width,
                    height,
                    fill,
                },
                Orientation::Down => SceneItem::Rect {
                    x: y,
                    y: x,
                    width: height,
                    height: width,
                    fill,
                },
                Orientation::Up => SceneItem::Rect {
                    x: y,
                    y: w - x - width,
                    width: height,
                    height: width,
                    fill,
                },
                Orientation::Right => SceneItem::Rect {
                    x,
                    y,
                    width,
                    height,
                    fill,
                },
            },
            SceneItem::Line {
                x1,
                y1,
                x2,
                y2,
                stroke,
                stroke_width,
            } => {
                let (x1, y1) = point(x1, y1);
                let (x2, y2) = point(x2, y2);
                SceneItem::Line {
                    x1,
                    y1,
                    x2,
                    y2,
                    stroke,
                    stroke_width,
                }
            }
            SceneItem::Text {
                x,
                y,
                text,
                font_size,
                color,
                anchor,
                is_tip_label,
                rotation_deg,
            } => {
                let (x, y) = point(x, y);
                SceneItem::Text {
                    x,
                    y,
                    text,
                    font_size,
                    color,
                    anchor: if swap_anchor { swap(anchor) } else { anchor },
                    is_tip_label,
                    rotation_deg: if rotate {
                        rotation_deg - 90.0
                    } else {
                        rotation_deg
                    },
                }
            }
            other @ (SceneItem::Arc { .. } | SceneItem::AnnularSector { .. }) => other,
        })
        .collect();
    Scene { canvas, items }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::layout::scene::Color;

    fn scene() -> Scene {
        Scene {
            canvas: Canvas {
                width: 100.0,
                height: 40.0,
            },
            items: vec![
                SceneItem::Rect {
                    x: 10.0,
                    y: 5.0,
                    width: 30.0,
                    height: 8.0,
                    fill: Color::black(),
                },
                SceneItem::Line {
                    x1: 12.0,
                    y1: 20.0,
                    x2: 70.0,
                    y2: 21.0,
                    stroke: Color::black(),
                    stroke_width: 1.0,
                },
                SceneItem::Text {
                    x: 74.0,
                    y: 24.0,
                    text: "a".into(),
                    font_size: 12.0,
                    color: Color::black(),
                    anchor: TextAnchor::Start,
                    is_tip_label: true,
                    rotation_deg: 0.0,
                },
            ],
        }
    }

    #[test]
    fn right_is_the_identity() {
        let s = orient_scene(scene(), Orientation::Right);
        assert_eq!(format!("{:?}", s.items), format!("{:?}", scene().items));
    }

    #[test]
    fn each_orientation_matches_the_table() {
        for (o, canvas, rect, line, text) in [
            (
                Orientation::Left,
                (100.0, 40.0),
                (60.0, 5.0, 30.0, 8.0),
                (88.0, 20.0, 30.0, 21.0),
                (26.0, 24.0, TextAnchor::End, 0.0),
            ),
            (
                Orientation::Down,
                (40.0, 100.0),
                (5.0, 10.0, 8.0, 30.0),
                (20.0, 12.0, 21.0, 70.0),
                (24.0, 74.0, TextAnchor::End, -90.0),
            ),
            (
                Orientation::Up,
                (40.0, 100.0),
                (5.0, 60.0, 8.0, 30.0),
                (20.0, 88.0, 21.0, 30.0),
                (24.0, 26.0, TextAnchor::Start, -90.0),
            ),
        ] {
            let s = orient_scene(scene(), o);
            assert_eq!((s.canvas.width, s.canvas.height), canvas, "{o:?}");
            match &s.items[0] {
                SceneItem::Rect {
                    x,
                    y,
                    width,
                    height,
                    ..
                } => assert_eq!((*x, *y, *width, *height), rect, "{o:?}"),
                other => panic!("{other:?}"),
            }
            match &s.items[1] {
                SceneItem::Line { x1, y1, x2, y2, .. } => {
                    assert_eq!((*x1, *y1, *x2, *y2), line, "{o:?}")
                }
                other => panic!("{other:?}"),
            }
            match &s.items[2] {
                SceneItem::Text {
                    x,
                    y,
                    anchor,
                    rotation_deg,
                    ..
                } => assert_eq!((*x, *y, *anchor, *rotation_deg), text, "{o:?}"),
                other => panic!("{other:?}"),
            }
        }
    }

    #[test]
    fn parse_round_trips_and_rejects() {
        for name in ORIENTATIONS {
            assert_eq!(Orientation::parse(name).unwrap().name(), name);
        }
        assert_eq!(
            Orientation::parse("top").unwrap_err(),
            "orientation must be one of ('right', 'down', 'left', 'up'), got 'top'"
        );
    }
}
