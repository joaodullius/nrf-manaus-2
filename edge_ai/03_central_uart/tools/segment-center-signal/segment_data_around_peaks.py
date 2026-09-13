# ORIGEM: copia literal de repositorio de terceiro — nao e codigo do curso.
#   Upstream: https://github.com/nordicsemi-neuton/segment-center-signal
#   Branch  : master · commit 5af1abe46f9500a5b21240ec4d57dc0c90caee55 (2025-12-02)
#   Copiado : 2026-09-01 — curso nrf-manaus-2, modulo edge_ai/03_central_uart
#   Alteracao local: este cabecalho e o BLOCO DE EXECUCAO do fim do arquivo.
#     As cinco funcoes do algoritmo (prepare_data, create_segmented_df,
#     segment_data, get_vector_of_work_axis, plot_segments, main, remove_nrows)
#     estao INTOCADAS. O bloco do fim, que no upstream e um exemplo com
#     sample_data.csv, foi adaptado para ler os CSVs do 03_central_uart.
#
# ATENCAO — LICENCA: o repositorio de origem NAO declara licenca (sem arquivo
# LICENSE, sem metadado de licenca no GitHub). A copia foi mantida aqui por
# decisao do curso, para o aluno nao depender de clone externo em sala.
# Ver ORIGEM.md nesta pasta.
#
# Como usar (e as armadilhas): ORIGEM.md nesta pasta, e o Passo 5 do
# ../../README.md.

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import os


def prepare_data(data, step, work_wind_size):
    """
    Prepares data for further analysis by creating a list of square root values
    based on sliding windows of a specified size.

    Parameters:
    -----------
    data : list
        A list of numerical values to be processed.
    step : int
        The step size between the start of each window.
    work_wind_size : int
        The size of the sliding window.

    Returns:
    --------
    list
        A list of square root values, one for each sliding window of the specified size.
    
    """
    prepared_data = []
    for i in range(0, len(data) - work_wind_size,  step):
        data_window = data[i : i + work_wind_size]
        prepared_data.append(np.sqrt( np.square(np.min(data_window)) + np.square(np.max(data_window)) ))
    return prepared_data


def create_segmented_df(df, segments, total_wind_size):
    """
    Creates a new DataFrame by segmenting the input DataFrame based on specified segments.

    Parameters:
    -----------
    df : pandas.DataFrame
        The input DataFrame to be segmented.
    segments : list of tuples
        A list of tuples, where each tuple represents a segment of the input DataFrame.
        Each tuple should contain two integers, representing the start and end indices of the segment.
    total_wind_size : int
        The total size of the window to be created around the center index of each segment.

    Returns:
    --------
    pandas.DataFrame
        A new DataFrame containing the rows of the input DataFrame that fall within the specified segments,
        as well as additional rows from the input DataFrame that fall within a window of size `total_wind_size`
        centered around the midpoint of each segment.
    
    """
    index_labled = 0
    columns = []

    for column in df:
        columns.append(column)
        df[column] = df[column].astype(int)

    df_segmented = pd.DataFrame(columns=columns)
    
    for s in segments:
        start_index, end_index = s
        index_center = int((end_index + start_index) / 2)
        for i in range(index_center - int(total_wind_size / 2), index_center + int(total_wind_size / 2)):
            row_data = df.iloc[i]
            df_segmented.loc[index_labled] = row_data
            index_labled += 1
    return df_segmented

def segment_data(data, work_wind_size, threshold_coef) :
    """
    Segments the input data based on zero-crossings above a specified threshold.

    Parameters:
    -----------
    data : list or numpy.ndarray
        The input data to be segmented.
    work_wind_size : int
        The size of the sliding window to be used for segmenting the data.
    threshold_coef : float
        The coefficient to be used for calculating the threshold for zero-crossing detection.
        The threshold is calculated as `threshold_coef` times the mean of the input data.

    Returns:
    --------
    list of tuples
        A list of tuples, where each tuple represents a segment of the input data.
        Each tuple contains two integers, representing the start and end indices of the segment.
        The indices are shifted by `work_wind_size / 2` to account for the sliding window.
    
    """
    global config
    threshold_coef = config['threshold_coef']

    # Calculate the mean of the data
    mean_data = np.mean(data)
    # Set the threshold for zero-crossing detection
    threshold = threshold_coef * mean_data

    i = 0
    segment_started = False
    start_index = 0
    end_index = 0
    segments = []
    
    for d in  data:
        i += 1
        if d > threshold:
            if not segment_started:
                segment_started = True
                start_index = i
        else :
            if segment_started:
                segment_started = False
                end_index = i

                segments.append((start_index + work_wind_size / 2, end_index + work_wind_size / 2))

    return segments

def get_vector_of_work_axis(df):
    """
    Extracts a vector of values from a specified column of a pandas DataFrame.

    Parameters:
    -----------
    df : pandas.DataFrame
        The input DataFrame from which to extract the vector of values.

    Returns:
    --------
    numpy.ndarray
        A one-dimensional numpy array containing the values from the specified column of the input DataFrame.
    
    """
    global config
    work_axis = config['work_axis']
    return df[work_axis].values.reshape(( len(df[work_axis]) ))


def plot_segments(df, n_segments=20):
    """
    Plots n_segments of a specified column of a pandas DataFrame.

    Parameters:
    -----------
    df : pandas.DataFrame
        The input DataFrame from which to extract the segments.

    Returns:
    --------
    None
        The function only generates a plot of the specified segments.
    
    """    
    global config
    total_wind_size = config['total_wind_size']
    work_axis = config['work_axis']
    for i in range(n_segments):
        start_ix = i*total_wind_size
        end_ix = i*total_wind_size + total_wind_size
        sample = df.loc[start_ix : end_ix]
        sample.plot(title=f'Start ix: {start_ix}, End ix: {end_ix}')


def main(df):
    global config
    step = config['step']
    work_wind_size = config['work_wind_size']
    total_wind_size = config['total_wind_size']
    threshold_coef = config['threshold_coef']

    axis_vector = get_vector_of_work_axis(df)
    # Substract DC offset
    dc = np.mean(axis_vector)
    data = axis_vector - dc
    data = prepare_data(data, step, work_wind_size)
    segments = segment_data(data, work_wind_size, threshold_coef)
    df_segmented = create_segmented_df(df, segments, total_wind_size)
    return df_segmented


def remove_nrows(df, nrows, first=True):
    """
    Removes the first n_windows from the input DataFrame.

    Parameters:
    -----------
    df : pandas.DataFrame
        The input DataFrame from which to remove the windows.
    nrows: int
        The number of rows to remove from the beginning of the DataFrame.
    first: bool
        If True, removes rows from the beginning of the DataFrame, else from end.

    Returns:
    --------
    pandas.DataFrame
        A new DataFrame with the first n_windows removed.
    
    """
    if first:
        df_cleaned = df.iloc[nrows : ].reset_index(drop=True)
    else:
        df_cleaned = df.iloc[ : -nrows].reset_index(drop=True)
    return df_cleaned


# =======================================================================
# BLOCO DE EXECUCAO — ADAPTADO PARA O CURSO
#
# Substitui o "MAIN SCRIPT EXECUTION EXAMPLE" do upstream. As cinco funcoes
# acima estao intocadas; so este bloco mudou. O que foi acrescentado:
#   - le o CSV do 03_central_uart (header do Lab) em vez do sample_data.csv
#   - caminhos resolvidos a partir da pasta do script, nao do cwd
#   - devolve os nomes de coluna do Lab antes de salvar (o upstream deixava aX..target)
#   - plt.show() no fim (o upstream criava as figuras e as descartava em silencio)
#   - diagnostico impresso: numero de gestos e checagem de multiplo da janela
#
# COMO USAR: ajuste o bloco "AJUSTE AQUI" e rode. Uma vez por gesto discreto.
#   python segment_data_around_peaks.py
# =======================================================================

import os

# ----------------------------- AJUSTE AQUI -----------------------------

# Classe a processar. Precisa existir em prep_dataset.py (CLASSES) e o arquivo
# de entrada tem que ser o dessa classe — o rotulo vem de dentro do CSV.
gesture = 'swipe_right'

# Arquivo bruto gravado pelo 03_central_uart (prep_dataset.py record).
ARQUIVO = r'dataset\swipe_right_2026-09-01_10-36-13.csv'

# Eixo usado SO para detectar os gestos. Nao chega no modelo.
# Escolhido por medicao nas gravacoes de 2026-09-01: os giros repousam em zero
# (desvio 1 no idle), entao a remocao de DC vira no-op e a pausa entre gestos da
# envelope quase nulo. Os acelerometros carregam a gravidade (acc_z ~ 10012 parado),
# que vira um degrau constante na pausa e degrada a deteccao.
#   gY -> desvio 3039 (swipe_right) e 3022 (swipe_left), 0.02%/0.43% no trilho
#   gZ -> plano B; maior no swipe_left (4611) mas 2.06% no trilho de +-1000 dps
WORK_AXIS = 'gY'

# Limiar de deteccao, em multiplos da media do envelope. E o parametro MAIS
# SENSIVEL do script, e o valor 0.5 do exemplo da Nordic e calibrado para a
# gravacao DELES — nao transporta.
#
# Calibrado por varredura no swipe_right de 2026-09-01 (janela 100, eixo gY),
# medindo onde o pico de |gY| cai dentro de cada segmento (50 = centro ideal):
#
#   coef   gestos   mediana   desvio   % em 40-59   % nas pontas
#   0.50      116        34     18.9        12.1%          14.7%   <- default Nordic
#   0.85      131        47     12.4        61.8%           3.8%
#   0.95      135        47      8.8        71.1%           0.7%   <- melhor
#   1.00      135        47     10.5        70.4%           2.2%
#   1.10      133        47     12.9        56.4%           4.5%
#   1.50       44        36     11.9        34.1%           4.5%
#   2.00        1         -        -            -              -
#
# Faixa util ~0.90 a 1.05. Acima disso o limiar passa do envelope dos gestos mais
# fracos e eles somem em silencio: 135 -> 44 -> 1 -> nenhum. Abaixo, os gestos se
# fundem e o recorte sai deslocado. Recalibre por gravacao — a intensidade do
# gesto muda o envelope.
#
# Criterio rapido: 5 min com gesto a cada ~2 s deve dar ~150 gestos.
#   gestos de menos -> baixe        gestos demais -> suba
THRESHOLD_COEF = 0.95

# Linhas descartadas do inicio e do fim (montagem/parada). 400 ~ 5 s.
nrows_to_remove = 400

# Janela do recorte. TEM que ser PAR: o recorte e
# range(centro - int(w/2), centro + int(w/2)), entao w=99 produz 98 linhas.
# Este valor precisa ser o MESMO "Window size" configurado no Edge AI Lab.
# Dali ele vai para o modelo gerado (INPUT_WINDOW_SIZE) e a app o le de la —
# nao ha numero cravado no firmware.
TRAINING_WINDOW_SIZE = 100

MOSTRAR_GRAFICOS = True

# --------------------------- fim do ajuste -----------------------------

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(AQUI, '..', '..'))   # 03_central_uart/
entrada = os.path.join(BASE, ARQUIVO)
saida_dir = os.path.join(BASE, 'dataset_centered')

assert TRAINING_WINDOW_SIZE % 2 == 0, \
    f'TRAINING_WINDOW_SIZE={TRAINING_WINDOW_SIZE} e impar: o recorte produziria ' \
    f'{2 * int(TRAINING_WINDOW_SIZE / 2)} linhas por segmento, nao {TRAINING_WINDOW_SIZE}.'

COLUNAS_LAB = ['acc_x', 'acc_y', 'acc_z', 'gyro_x', 'gyro_y', 'gyro_z', 'class']

df = pd.read_csv(entrada, on_bad_lines='skip')
assert df.isnull().sum().sum() == 0
assert list(df.columns) == COLUNAS_LAB, \
    f'header inesperado em {entrada}: {list(df.columns)}'

rotulo = df['class'].iloc[0]
assert (df['class'] == rotulo).all(), 'o arquivo tem mais de uma classe'

linhas_brutas = len(df)

# Nomes internos do script (as funcoes referenciam work_axis por esse nome).
df.columns = ['aX', 'aY', 'aZ', 'gX', 'gY', 'gZ', 'target']

df = remove_nrows(df, nrows_to_remove, first=True)
df = remove_nrows(df, nrows_to_remove, first=False)
df.reset_index(drop=True, inplace=True)

config = {
    'work_axis': WORK_AXIS,
    'work_wind_size': int(TRAINING_WINDOW_SIZE * 0.95),
    'total_wind_size': TRAINING_WINDOW_SIZE,
    'threshold_coef': THRESHOLD_COEF,
    'step': 1,
}

if MOSTRAR_GRAFICOS:
    plot_segments(df, n_segments=5)

print(f'  classe    {gesture} (= {rotulo})')
print(f'  entrada   {entrada}')
print(f'  linhas    {linhas_brutas} brutas -> {len(df)} apos aparar {nrows_to_remove} de cada ponta')
print(f'  eixo      {WORK_AXIS} · threshold_coef {THRESHOLD_COEF} · janela {TRAINING_WINDOW_SIZE}')
print('  segmentando (lento: o upstream faz df.loc[i] = row em laco) ...')

df_segmented = main(df)

if MOSTRAR_GRAFICOS:
    plot_segments(df_segmented, n_segments=5)

# Devolve o header que o Lab e o prep_dataset.py merge esperam.
df_segmented.columns = COLUNAS_LAB

os.makedirs(saida_dir, exist_ok=True)
saida = os.path.join(saida_dir, f'{gesture}.csv')
df_segmented.to_csv(saida, index=False)

n = len(df_segmented)
gestos = n / TRAINING_WINDOW_SIZE
print()
print(f'  gravado   {n} linhas -> {saida}')
print(f'  gestos    {gestos:.0f} detectados')
print(f'  multiplo de {TRAINING_WINDOW_SIZE}: {n % TRAINING_WINDOW_SIZE == 0}')
if not 50 <= gestos <= 400:
    print(f'  ATENCAO   {gestos:.0f} gestos em ~5 min esta fora do esperado (~150).')
    print(f'            calibre o THRESHOLD_COEF: de menos -> baixe, demais -> suba.')
print()
print('  Confira os graficos: depois da segmentacao o pico tem que estar no MEIO')
print('  de cada janela. A contagem sozinha engana.')

if MOSTRAR_GRAFICOS:
    plt.show()

