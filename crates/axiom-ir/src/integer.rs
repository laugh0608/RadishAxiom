//! 保留任意精度十进制文本的数学整数。这里只提供规范词法与精确比较，不提供算术。

use std::cmp::Ordering;

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Integer(String);

impl Integer {
    /// 只接受 `0|-?[1-9][0-9]*`；不转为固定宽度整数或浮点数。
    pub fn parse(text: &str) -> Option<Self> {
        if text == "0" {
            return Some(Self(text.to_owned()));
        }
        let digits = text.strip_prefix('-').unwrap_or(text).as_bytes();
        if !matches!(digits.first(), Some(b'1'..=b'9')) || !digits.iter().all(u8::is_ascii_digit) {
            return None;
        }
        Some(Self(text.to_owned()))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }

    pub fn is_negative(&self) -> bool {
        self.0.starts_with('-')
    }
}

impl Ord for Integer {
    fn cmp(&self, other: &Self) -> Ordering {
        let left_negative = self.is_negative();
        let right_negative = other.is_negative();
        match (left_negative, right_negative) {
            (true, false) => Ordering::Less,
            (false, true) => Ordering::Greater,
            _ => {
                let left = self.0.trim_start_matches('-');
                let right = other.0.trim_start_matches('-');
                let magnitude = left.len().cmp(&right.len()).then_with(|| left.cmp(right));
                if left_negative {
                    magnitude.reverse()
                } else {
                    magnitude
                }
            }
        }
    }
}

impl PartialOrd for Integer {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}
