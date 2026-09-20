/** A dictated message with every number marked, for the doctor to check before sending. */

// A number on its own, not the "1" inside "HbA1c".
const NUMBER = /(?<![\p{L}\d])(\d+(?:[.,]\d+)?)/u

export function HighlightNumbers({ text }: { text: string }) {
  return (
    <>
      {text.split(NUMBER).map((piece, index) =>
        index % 2 === 1 ? (
          <mark key={index} className="rounded-sm bg-check-fill px-1 font-bold text-check-ink outline-2 outline-check-line">
            {piece}
          </mark>
        ) : (
          piece
        ),
      )}
    </>
  )
}
