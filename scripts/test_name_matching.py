import sys
from pprint import pprint


def main() -> int:
    try:
        from backend.shared_functions.helpers_repo import HelpersRepo
        hr = HelpersRepo()

        cases = [
            (
                "basic_partial_en",
                "pipo",
                ["pipo inzaghi", "pipo offisde inzaghi", "Not provided", "pipo ppp"],
            ),
            (
                "case_insensitive",
                "PiPo",
                ["PIPO Inzaghi", "pIpo test", "random"],
            ),
            (
                "titles_suffixes_en",
                "Mr Pipo",
                ["mr pipo inzaghi jr", "mrs pipo", "dr x", "Not provided"],
            ),
            (
                "nepali_partial",
                "राम",
                ["राम शर्मा", "श्याम शर्मा", "हरि थापा"],
            ),
            (
                "nepali_title_suffix",
                "श्री राम जी",
                ["राम शर्मा", "श्री राम थापा ज्यू", "राम"],
            ),
            (
                "noise_tokens",
                "pipo",
                ["pipo - test", "pipo, inc.", "(pipo)", "pi-po"],
            ),
            (
                "short_queries",
                "pi",
                ["pipo", "pia", "pip", "Not provided"],
            ),
            (
                "numeric_only",
                "1234",
                ["pipo 1234", "1234 pipo", "abcd"],
            ),
            (
                "empty_and_none",
                "",
                ["pipo", ""],
            ),
            (
                "skip_values",
                "Not provided",
                ["Not provided", "Skip", "pipo"],
            ),
            (
                "multiword_query",
                "pipo inz",
                ["pipo inzaghi", "pipo ppp", "inzaghi pipo"],
            ),
        ]

        results = {}
        for name, query, reference in cases:
            try:
                matches = hr.match_full_name_list(query, reference)
            except Exception as e:
                matches = f"ERROR: {e}"
            results[name] = {
                "query": query,
                "reference": reference,
                "matches": matches,
            }

        pprint(results, width=120)
        return 0
    except Exception as e:
        print(f"❌ Test run failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())


