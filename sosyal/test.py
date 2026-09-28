import sosyal, sys
from concurrent.futures import ThreadPoolExecutor
oyun, tur = sys.argv[1], sys.argv[2]
def one(s):
    try:
        sosyal.uret(oyun, tur, sablon=s, muzik=sosyal.muzikler(oyun)[0], kare=True, durum_guncelle=False); return s+" ok"
    except Exception as e: return s+" HATA "+str(e)[-300:]
with ThreadPoolExecutor(4) as ex:
    for r in ex.map(one, sosyal.SABLONLAR): print(r)
