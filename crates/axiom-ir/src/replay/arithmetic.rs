//! 十进制有界工作；宿主整数只用于单个 digit / 有界下标。
use super::{Budget, ReplayError, ReplayResource as R, Result};
use crate::integer::Integer;
use std::cmp::Ordering;

pub(super) fn parse(s: &str, b: &mut Budget) -> Result<Integer> {
    b.observe(R::IntegerDigits, s.trim_start_matches('-').len())?;
    b.charge(R::ValueCells, s.len())?;
    b.charge(R::DigitWork, s.len())?;
    Integer::parse(s).ok_or(ReplayError::Internal("checked decimal"))
}
pub(super) fn compare(a: &Integer, c: &Integer, b: &mut Budget) -> Result<Ordering> {
    let work = a
        .as_str()
        .len()
        .checked_add(c.as_str().len())
        .ok_or_else(|| b.error(R::DigitWork))?;
    b.charge(R::DigitWork, work)?;
    Ok(a.cmp(c))
}
pub(super) fn calculate(
    a: &Integer,
    c: &Integer,
    subtract: bool,
    b: &mut Budget,
) -> Result<Integer> {
    let x = a.as_str().trim_start_matches('-').as_bytes();
    let y = c.as_str().trim_start_matches('-').as_bytes();
    let sx = a.is_negative();
    let sy = c.is_negative() ^ subtract;
    let n = x.len().max(y.len());
    let workspace = n
        .checked_add(2)
        .and_then(|v| v.checked_mul(3))
        .ok_or_else(|| b.error(R::ValueCells))?;
    b.charge(R::ValueCells, workspace)?;
    let mut digits = Vec::with_capacity(n + 2);
    let negative;
    if sx == sy {
        negative = sx;
        let mut carry = 0u8;
        for i in 0..n {
            b.charge(R::DigitWork, 2)?;
            let l = x
                .get(x.len().wrapping_sub(i + 1))
                .map(|v| v - b'0')
                .unwrap_or(0);
            let r = y
                .get(y.len().wrapping_sub(i + 1))
                .map(|v| v - b'0')
                .unwrap_or(0);
            let sum = l + r + carry;
            digits.push(b'0' + sum % 10);
            carry = sum / 10;
        }
        if carry != 0 {
            b.charge(R::DigitWork, 1)?;
            digits.push(b'0' + carry);
        }
    } else {
        b.charge(
            R::DigitWork,
            x.len()
                .checked_add(y.len())
                .ok_or_else(|| b.error(R::DigitWork))?,
        )?;
        let order = x.len().cmp(&y.len()).then_with(|| x.cmp(y));
        let (large, small) = if order == Ordering::Less {
            (y, x)
        } else {
            (x, y)
        };
        negative = if order == Ordering::Less { sy } else { sx };
        let mut borrow = 0i16;
        for i in 0..large.len() {
            b.charge(R::DigitWork, 2)?;
            let l = i16::from(large[large.len() - 1 - i] - b'0');
            let r = small
                .get(small.len().wrapping_sub(i + 1))
                .map(|v| i16::from(v - b'0'))
                .unwrap_or(0);
            let mut digit = l - r - borrow;
            borrow = 0;
            if digit < 0 {
                digit += 10;
                borrow = 1;
            }
            digits.push(b'0' + u8::try_from(digit).expect("digit"));
        }
        while digits.len() > 1 && digits.last() == Some(&b'0') {
            b.charge(R::DigitWork, 1)?;
            digits.pop();
        }
    }
    b.observe(R::IntegerDigits, digits.len())?;
    b.charge(R::DigitWork, digits.len())?;
    digits.reverse();
    if negative && digits != b"0" {
        b.charge(R::DigitWork, digits.len())?;
        digits.insert(0, b'-');
    }
    let s = String::from_utf8(digits).expect("ASCII digits");
    parse(&s, b)
}
