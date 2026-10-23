import os
import ccxt
import pandas as pd

# =====================================================================
# 1. CONEXIÓN OFICIAL A BITVAVO (PARES DIRECTOS EN EUROS + MI-CA ID)
# =====================================================================
OPERATOR_ID = 1001  # Identificador obligatorio exigido por Bitvavo API para bots

exchange = ccxt.bitvavo({
    'apiKey': os.environ.get('BITVAVO_API_KEY'),
    'secret': os.environ.get('BITVAVO_SECRET_KEY'),
    'enableRateLimit': True,
    'options': {'operatorId': OPERATOR_ID},
})

MONEDA_BASE = 'EUR'
RIESGO_PORCENTAJE = 0.02  # 2% de tu cuenta total arriesgado por operación (1R = 2€ sobre 100€)
TEMPORALIDAD = '2h'
MINIMO_ORDEN_EUR = 5.5    # El mínimo de Bitvavo son 5.00 €, ponemos 5.50 € de margen seguro

# =====================================================================
# 2. MATRIZ MULTI-MOTOR DE CRIPTOMONEDAS (CONFIGURACIÓN INDIVIDUAL)
# =====================================================================
# Aquí cada cripto tiene su propio código/ajustes.
# - SOL, ETH y SUI están en 'activo': True con tus parámetros ganadores (17, 1.5, 2.35).
# - BTC y XRP están en 'activo': False como plantilla con Filtro ADX activado.
#   Cuando encuentres en TradingView los números ideales de una nueva cripto,
#   solo tienes que poner 'activo': True o añadir una línea igual a esta tabla.

CONFIG_MONEDAS = {
    # --- TUS 3 MONEDAS BASE ---
    'SOL/EUR': {
        'activo': True,
        'donchian': 20,
        'vol_mult': 1.5,
        'atr_mult': 2.35,
        'usar_adx': False,
        'adx_min': 20,
    },
    'ETH/EUR': {
        'activo': True,
        'donchian': 20,
        'vol_mult': 1.5,
        'atr_mult': 2.35,
        'usar_adx': False,
        'adx_min': 20,
    },
    'SUI/EUR': {
        'activo': True,
        'donchian': 20,
        'vol_mult': 1.5,
        'atr_mult': 2.35,
        'usar_adx': False,
        'adx_min': 20,
    },
    
    # --- TUS 4 NUEVAS CAMPEONAS TESTEADAS ---
    'PEPE/EUR': {
        'activo': True,
        'donchian': 7,
        'vol_mult': 2.3,
        'atr_mult': 2.65,
        'usar_adx': False,
        'adx_min': 20,
    },
    'AAVE/EUR': {
        'activo': True,
        'donchian': 25,
        'vol_mult': 1.5,
        'atr_mult': 1.35,
        'usar_adx': False,
        'adx_min': 20,
    },
    'SEI/EUR': {
        'activo': True,
        'donchian': 7,
        'vol_mult': 1.7,
        'atr_mult': 2.60,
        'usar_adx': False,
        'adx_min': 20,
    },
    'STX/EUR': {
        'activo': True,
        'donchian': 22,
        'vol_mult': 1.7,
        'atr_mult': 1.85,
        'usar_adx': False,
        'adx_min': 20,
    },
}

# =====================================================================
# 3. MOTOR MATEMÁTICO EXACTO DE TRADINGVIEW (EMA, ATR WILDER, ADX, DONCHIAN)
# =====================================================================
def calcular_indicadores(df, cfg):
    # EMA de 200 periodos (Filtro de tendencia alcista)
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # Media de Volumen de 20 periodos
    df['vol_ma'] = df['volume'].rolling(20).mean()
    
    # Canal de Ruptura Donchian (mirando las N velas anteriores cerradas)
    df['max_canal'] = df['high'].shift(1).rolling(cfg['donchian']).max()
    
    # ATR de 14 periodos (Fórmula RMA exacta de Wilder usada en TradingView)
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - df['close'].shift(1)).abs()
    tr3 = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = tr.ewm(alpha=1/14, adjust=False).mean()
    
    # ADX de 14 periodos (Fórmula exacta de TradingView para el Motor B)
    up = df['high'].diff()
    down = -df['low'].diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    plus_di = 100 * (plus_dm.ewm(alpha=1/14, adjust=False).mean() / df['atr'])
    minus_di = 100 * (minus_dm.ewm(alpha=1/14, adjust=False).mean() / df['atr'])
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).fillna(0)
    df['adx'] = dx.ewm(alpha=1/14, adjust=False).mean()
    
    return df

# =====================================================================
# 4. MEMORIA DEL BOT: SABER EL PRECIO MÁXIMO DESDE LA COMPRA
# =====================================================================
def obtener_maximo_desde_compra(par, df):
    try:
        # Pregunta a Bitvavo cuándo fue nuestra última compra en esta moneda
        mis_compras = exchange.fetch_my_trades(par, limit=5)
        compras = [t for t in mis_compras if t['side'] == 'buy']
        if compras:
            ts_ultima_compra = compras[-1]['timestamp']
            velas_desde_compra = df[df['timestamp'] >= (ts_ultima_compra - 7200000)]
            if not velas_desde_compra.empty:
                return float(velas_desde_compra['high'].max())
    except Exception:
        pass
    return float(df['high'].iloc[-2:].max())

# =====================================================================
# 5. CALCULAR EL VALOR TOTAL DE LA CARTERA Y EL 2% DE RIESGO (1R)
# =====================================================================
def obtener_capital_y_riesgo(balance):
    eur_total = float(balance['total'].get(MONEDA_BASE, 0.0))
    for par in CONFIG_MONEDAS.keys():
        moneda = par.split('/')[0]
        cantidad = float(balance['total'].get(moneda, 0.0))
        if cantidad > 0:
            try:
                precio = float(exchange.fetch_ticker(par)['last'])
                eur_total += (cantidad * precio)
            except Exception:
                pass
    riesgo_1r = eur_total * RIESGO_PORCENTAJE
    return eur_total, riesgo_1r

# =====================================================================
# 6. EJECUCIÓN PRINCIPAL DEL BOT FRANCOTIRADOR
# =====================================================================
def ejecutar_francotirador():
    exchange.load_markets()
    balance = exchange.fetch_balance()
    capital_total, riesgo_1r = obtener_capital_y_riesgo(balance)
    eur_libre = float(balance['free'].get(MONEDA_BASE, 0.0))
    
    print("=================================================================")
    print(f"💶 Capital Total: {capital_total:.2f} EUR | Libre: {eur_libre:.2f} EUR | Riesgo 2% (1R): {riesgo_1r:.2f} EUR")
    print("=================================================================")
    
    for par, cfg in CONFIG_MONEDAS.items():
        if not cfg['activo']:
            continue
            
        try:
            moneda = par.split('/')[0]
            cantidad_actual = float(balance['free'].get(moneda, 0.0))
            precio_actual = float(exchange.fetch_ticker(par)['last'])
            valor_posicion_eur = cantidad_actual * precio_actual
            
            # Descargar las últimas 250 velas de 2 horas desde Bitvavo
            bars = exchange.fetch_ohlcv(par, timeframe=TEMPORALIDAD, limit=250)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df = calcular_indicadores(df, cfg)
            
            # Leemos la última vela cerrada de 2h (-2)
            v = df.iloc[-2]
            distancia_stop = float(v['atr'] * cfg['atr_mult'])
            
            # -----------------------------------------------------------------
            # CASO A: YA TENEMOS LA CRIPTO COMPRADA -> VIGILAR TRAILING STOP
            # -----------------------------------------------------------------
            if valor_posicion_eur >= MINIMO_ORDEN_EUR:
                maximo_alcanzado = obtener_maximo_desde_compra(par, df)
                stop_movil_amarillo = maximo_alcanzado - distancia_stop
                
                print(f"🔒 [{par}] EN CARTERA ({valor_posicion_eur:.2f} €) | Precio: {precio_actual} € | Máx: {maximo_alcanzado} € | Trailing Stop: {stop_movil_amarillo:.4f} €")
                
                # Si el precio actual cae por debajo de la línea amarilla (Trailing Stop), vendemos
                if precio_actual <= stop_movil_amarillo:
                    qty_vender = float(exchange.amount_to_precision(par, cantidad_actual))
                    exchange.create_order(par, 'market', 'sell', qty_vender, None, {'operatorId': OPERATOR_ID})
                    print(f"🎯 [{par}] ¡TRAILING STOP EJECUTADO! Posición cerrada a {precio_actual} € protegiendo beneficios.")
            
            # -----------------------------------------------------------------
            # CASO B: NO TENEMOS LA CRIPTO -> BUSCAR DISPARO DEL FRANCOTIRADOR
            # -----------------------------------------------------------------
            else:
                hay_gasolina = v['volume'] > (v['vol_ma'] * cfg['vol_mult'])
                hay_tendencia_adx = (not cfg['usar_adx']) or (v['adx'] > cfg['adx_min'])
                
                disparo_largo = (
                    v['close'] > v['ema200'] and
                    v['close'] > v['max_canal'] and
                    hay_gasolina and
                    hay_tendencia_adx
                )
                
                if disparo_largo:
                    # Calcular tamaño exacto para que si cae 'distancia_stop', solo perdamos 1R (2% = 2€)
                    qty_calculada = riesgo_1r / distancia_stop
                    coste_eur = qty_calculada * precio_actual
                    
                    # Ajustar si el coste supera el saldo libre disponible
                    if coste_eur > (eur_libre * 0.98):
                        qty_calculada = (eur_libre * 0.98) / precio_actual
                        coste_eur = qty_calculada * precio_actual
                        
                    if coste_eur >= MINIMO_ORDEN_EUR:
                        qty_compra = float(exchange.amount_to_precision(par, qty_calculada))
                        stop_inicial = precio_actual - distancia_stop
                        
                        exchange.create_order(par, 'market', 'buy', qty_compra, None, {'operatorId': OPERATOR_ID})
                        eur_libre -= coste_eur
                        print(f"🚀 ¡DISPARO EN {par}! Comprado {qty_compra} ({coste_eur:.2f} €) a {precio_actual} € | Trailing Stop inicial en: {stop_inicial:.4f} €")
                    else:
                        print(f"⚠️ [{par}] Señal de compra detectada, pero saldo libre insuficiente ({eur_libre:.2f} €).")
                else:
                    estado_adx = f" | ADX: {v['adx']:.1f}" if cfg['usar_adx'] else ""
                    print(f"👀 [{par}] Vigilando (Precio: {precio_actual} € | Techo Ruptura: {v['max_canal']:.4f} €{estado_adx}) -> Sin disparo.")
                    
        except Exception as e:
            print(f"❌ Error procesando {par}: {e}")

if __name__ == "__main__":
    ejecutar_francotirador()
