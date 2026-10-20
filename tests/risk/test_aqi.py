import pytest

from risk.aqi import PM10, PM25, band, india_aqi, sub_index

PM25_CASES = {0: 0, 30: 50, 30.4: 50, 30.5: 51, 31: 51, 45: 75, 53: 88, 60: 100, 61: 101, 75: 149,
              90: 200, 91: 201, 92: 204, 95: 215, 120: 300, 121: 301, 250: 400, 251: 401,
              380: 500, 600: 500}
PM10_CASES = {0: 0, 50: 50, 51: 51, 100: 100, 101: 101, 175: 150, 250: 200, 251: 201, 255: 205,
              300: 250, 350: 300, 351: 301, 430: 400, 431: 401, 510: 500, 900: 500}


@pytest.mark.parametrize(("conc", "want"), PM25_CASES.items())
def test_pm25(conc, want):
    assert sub_index(conc, PM25) == want


@pytest.mark.parametrize(("conc", "want"), PM10_CASES.items())
def test_pm10(conc, want):
    assert sub_index(conc, PM10) == want


def test_india_aqi():
    assert india_aqi(95, 175) == 215
    assert india_aqi(53, 60) == 88
    assert india_aqi(None, 80) == 80
    assert india_aqi(None, None) is None


@pytest.mark.parametrize(("aqi", "want"), [
    (0, "Good"), (50, "Good"), (51, "Satisfactory"), (100, "Satisfactory"), (101, "Moderate"),
    (200, "Moderate"), (201, "Poor"), (300, "Poor"), (301, "Very poor"), (400, "Very poor"),
    (401, "Severe"), (500, "Severe")])
def test_band(aqi, want):
    assert band(aqi) == want
