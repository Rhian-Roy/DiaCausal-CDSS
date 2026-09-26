# Attribution

**Profanity word lists** in `shared/guard_rules/rules.v1.json` are derived from the
*List of Dirty, Naughty, Obscene and Otherwise Bad Words* (files `en` and `hi`),
https://github.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words,
licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).
Changes made by DiaCausal: clinical and descriptive terms removed (listed under
`profanity.removed_from_source`), a medical allowlist added.

## WHO 2018 guideline (RAG corpus)

World Health Organization. *Guidelines on second- and third-line medicines and type of insulin for
the control of blood glucose levels in non-pregnant adults with diabetes mellitus.* Geneva: WHO; 2018.
Licence: CC BY-NC-SA 3.0 IGO (https://creativecommons.org/licenses/by-nc-sa/3.0/igo).
Changes made by DiaCausal: text of PDF pages 7–26 extracted (layout, contents, references and
appendices removed) into `diacausal_rag/corpus/who_2018_second_line.txt`, shared under the same
licence for non-commercial use. WHO does not endorse DiaCausal or any product.

## FDA Drug Safety Communications (RAG corpus)

US Food and Drug Administration texts (US federal government works, not subject to copyright in the
US): the communications listed as S08 and S19–S23 in `RAG/sources.csv`. Brand-name tables and reference
lists removed. They describe US labelling, not Indian CDSCO labelling.
