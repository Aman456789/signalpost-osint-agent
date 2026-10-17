from decimal import Decimal

from validators.identity_lock import check_identity

LEGAL_NAME = "EKSEMPEL KONSULT AS"
ORGNR = "923456783"


def identity(url, text, **overrides):
    args = dict(official_domain="eksempelkonsult.no", orgnr=ORGNR, legal_name=LEGAL_NAME, town="OSLO")
    return check_identity(url, text, **{**args, **overrides})


def test_official_domain_and_orgnr_pass():
    result = identity("https://www.eksempelkonsult.no/om-oss", "Org.nr 923 456 783 MVA")
    assert result.g == 1
    assert result.score == Decimal("0.85")


def test_official_domain_and_name_with_town_pass():
    result = identity("https://eksempelkonsult.no/", "Eksempel Konsult AS holder til i Oslo.")
    assert result.g == 1
    assert result.score == Decimal("0.75")


def test_domain_alone_is_not_enough():
    result = identity("https://eksempelkonsult.no/", "Velkommen til oss.")
    assert result.score == Decimal("0.6")
    assert result.g == 0


def test_name_without_town_is_not_enough():
    result = identity("https://eksempelkonsult.no/", "Eksempel Konsult AS leverer rådgivning.")
    assert result.g == 0


def test_subdomain_of_the_official_domain_passes():
    assert identity("https://blogg.eksempelkonsult.no/", "923456783").g == 1


def test_news_page_on_another_domain_fails_even_with_everything_on_it():
    text = "Eksempel Konsult AS i Oslo, org.nr 923 456 783."
    result = identity("https://avisa.no/nyheter/sammenslaing", text)
    assert result.g == 0
    assert result.domain_ok is False
    assert result.score == Decimal("0.4")


def test_look_alike_domain_fails():
    assert identity("https://eksempelkonsult.no.evil.com/", "923456783").g == 0
    assert identity("https://xeksempelkonsult.no/", "923456783").g == 0


def test_orgnr_inside_a_longer_number_does_not_count():
    result = identity("https://eksempelkonsult.no/", "Ref 19234567831 og 9234567830")
    assert result.orgnr_on_page is False
    assert result.g == 0


def test_orgnr_formats():
    for text in ("923456783", "923 456 783", "NO 923.456.783 MVA"):
        assert identity("https://eksempelkonsult.no/", text).orgnr_on_page


def test_look_alike_company_does_not_pass_as_the_other():
    # "Eksempel Fisk AS" must not unlock the identity of "Eksempel Fisk Drift AS" and the reverse
    fisk = "Eksempel Fisk AS, Bergen. Org.nr 974 760 673"
    drift = "Eksempel Fisk Drift AS, Tromsø. Org.nr 983 887 457"
    for_fisk = dict(official_domain="eksempelfisk.no", orgnr="974760673", legal_name="EKSEMPEL FISK AS", town="BERGEN")
    for_drift = dict(official_domain="eksempelfiskdrift.no", orgnr="983887457", legal_name="EKSEMPEL FISK DRIFT AS", town="TROMSØ")
    assert check_identity("https://eksempelfisk.no/", fisk, **for_fisk).g == 1
    assert check_identity("https://eksempelfisk.no/", drift, **for_fisk).g == 0
    assert check_identity("https://eksempelfiskdrift.no/", drift, **for_drift).g == 1
    assert check_identity("https://eksempelfiskdrift.no/", fisk, **for_drift).g == 0


def test_missing_registry_data_never_passes():
    result = identity("https://eksempelkonsult.no/", "Eksempel Konsult AS Oslo", legal_name=None, town=None)
    assert result.g == 0
    assert identity("https://eksempelkonsult.no/", "923456783", official_domain=None).g == 0
