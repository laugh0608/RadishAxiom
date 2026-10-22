//! 有界十进制数学整数；不使用宿主整数承载值。
use super::{Meter, R, Result};
use std::cmp::Ordering;
pub(super) fn compare_bytes(a: &str, b: &str, m: &mut Meter) -> Result<Ordering> {
    m.work(1)?;
    for (a, b) in a.bytes().zip(b.bytes()) {
        m.work(2)?;
        let cmp = a.cmp(&b);
        if !cmp.is_eq() {
            return Ok(cmp);
        }
    }
    Ok(a.len().cmp(&b.len()))
}
fn magnitude(a: &str, b: &str, m: &mut Meter) -> Result<Ordering> {
    m.work(1)?;
    if a.len() != b.len() {
        Ok(a.len().cmp(&b.len()))
    } else {
        compare_bytes(a, b, m)
    }
}
pub(super) fn compare(a: &str, b: &str, m: &mut Meter) -> Result<Ordering> {
    m.work(1)?;
    let (an, bn) = (a.starts_with('-'), b.starts_with('-'));
    if an != bn {
        return Ok(if an {
            Ordering::Less
        } else {
            Ordering::Greater
        });
    }
    let cmp = magnitude(a.trim_start_matches('-'), b.trim_start_matches('-'), m)?;
    Ok(if an { cmp.reverse() } else { cmp })
}
pub(super) fn calculate(a: &str, b: &str, subtract: bool, m: &mut Meter) -> Result<String> {
    m.work(1)?;
    let an = a.starts_with('-');
    let bn = b.starts_with('-') ^ subtract;
    let (a, b) = (a.trim_start_matches('-'), b.trim_start_matches('-'));
    let adding = an == bn;
    let order = magnitude(a, b, m)?;
    let negative = if adding || !order.is_lt() { an } else { bn };
    let capacity = m.add(a.len().max(b.len()), 1, R::TemporaryBytes)?;
    m.bytes(capacity)?;
    let mut reversed = Vec::with_capacity(capacity);
    if adding {
        let mut carry = 0u8;
        let mut ai = a.bytes().rev();
        let mut bi = b.bytes().rev();
        for _ in 0..a.len().max(b.len()) {
            m.work(3)?;
            let sum = ai.next().map_or(0, |b| b - b'0') + bi.next().map_or(0, |b| b - b'0') + carry;
            reversed.push(b'0' + sum % 10);
            carry = sum / 10;
        }
        if carry != 0 {
            reversed.push(b'0' + carry);
        }
    } else {
        let (large, small) = if order.is_lt() { (b, a) } else { (a, b) };
        let mut small = small.bytes().rev();
        let mut borrow = 0i8;
        for digit in large.bytes().rev() {
            m.work(3)?;
            let difference =
                (digit - b'0') as i8 - small.next().map_or(0, |b| b - b'0') as i8 - borrow;
            borrow = i8::from(difference < 0);
            reversed.push(
                b'0' + (if difference < 0 {
                    difference + 10
                } else {
                    difference
                }) as u8,
            );
        }
        while reversed.len() > 1 && reversed.last() == Some(&b'0') {
            m.work(1)?;
            reversed.pop();
        }
    }
    let digits = reversed.len();
    m.charge(R::IntegerDigits, digits)?;
    let negative = negative && !(digits == 1 && reversed[0] == b'0');
    let length = m.add(digits, usize::from(negative), R::TemporaryBytes)?;
    m.bytes(length)?;
    let mut result = String::with_capacity(length);
    if negative {
        result.push('-');
    }
    for b in reversed.iter().rev() {
        m.work(1)?;
        result.push(char::from(*b));
    }
    Ok(result)
}
