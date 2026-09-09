# O teste do deslocamento — RTK com base própria

09/09/2026, janela entre os dois prédios. Dois ZED-X20P (HPG 2.11), antenas
ANN-MB2 sobre plano de terra, **1,5 m entre elas**. Um vira base (survey-in,
RTCM na UART2), o outro vira rover.

O rover gravou contínuo e carimbado em `rover.tsv`; `_marcas.json` guarda as
janelas. `desloca.png` é a figura. Reproduzir com:

```
python ../../tools/desloca.py marcas saida.png
```

## O que o teste prova, que o CEP não prova

CEP mede **repetibilidade**: o quanto as posições se agrupam. Um receptor pode
repetir lindamente um número e estar medindo a coisa errada. Mover a antena por
uma distância conhecida e ver a nuvem inteira andar junto é o que separa
*preciso* de *correto* — e é barato.

| | |
|---|---|
| P1, antes de mover | 908 épocas, 100% RTK fixo, CEP50 6,0 cm |
| P2, depois de mover | 908 épocas, 100% RTK fixo, CEP50 2,4 cm |
| **deslocamento medido** | **10,4 cm**, rumo 33° (norte +8,7, leste +5,6) |
| **incerteza** | **±1,9 cm** |
| veredito | 5,5× a própria incerteza — conclusivo |

O movimento anotado à mão foi de ~14 cm. A diferença de 3,6 cm não fecha dentro
da incerteza e fica registrada como divergência, não arredondada para longe: as
candidatas são a régua (estimativa a olho), uma componente vertical ou rotação
no movimento, e a quantização da NMEA.

## As três coisas que este teste ensinou

### Flutuante não mede deslocamento

A primeira captura foi perdida inteira. Ela rodou em RTK **flutuante**, e quando
o receptor finalmente fixou, a solução **saltou cerca de 1 metro**. Esse salto
teria engolido os 14 cm sem deixar rastro.

O motivo: em flutuante as ambiguidades de fase são estimativas contínuas, e a
posição fica deslocada por um viés que só some quando elas travam em inteiros.
Duas janelas em flutuante não são comparáveis nem entre si, porque o viés muda.

**Só compare posições dentro do regime fixo.** É por isso que `desloca.py` recorta
as épocas de qualidade 4 e avisa quando não há 30 delas.

### Entrar no fixo é caro; manter é barato

| | |
|---|---|
| tempo até fixar, com o filtro frio | **1149 s (19 min)** |
| sobreviveu a mover a antena "aos trancos" | sim, sem cair uma época |
| tempo até fixar, com o receptor já quente | **2 s** |

O custo está em resolver a ambiguidade da primeira vez. Depois disso o
travamento é robusto — inclusive a movimento brusco, desde que o céu não seja
bloqueado. Numa demo, isso significa: ligue cedo, e não desligue.

### A incerteza do centroide precisa ser medida, não calculada

A tentação é dizer que o erro do centroide cai por raiz de n: com 900 épocas,
3 cm de dispersão daria 1 mm. **Está errado por uma ordem de grandeza.** Épocas
consecutivas de GNSS compartilham a mesma ionosfera, o mesmo multipath e as
mesmas ambiguidades — não são amostras independentes.

Medido: os centroides de 1 minuto se espalham **6,9 cm** entre si, e a incerteza
real do centroide de 15 minutos é **±1,8 cm** — dezoito vezes maior que a conta
ingênua. `desloca.py` estima isso pelo espalhamento das sub-janelas, e é esse
número que entra no veredito.

## Absoluto e relativo não são a mesma coisa

O survey-in fixou a base com **9,6 m** de exatidão absoluta — normal sob céu
obstruído, onde a precisão estagna em vez de melhorar. Isso não afeta o teste em
nada: se a base está 10 m fora do lugar, as duas nuvens do rover se deslocam
pelos **mesmos** 10 m, e o vetor entre elas continua centimétrico.

RTK entrega **vetor exato em relação à base**, não posição exata no mundo. Para
ter as duas, é preciso uma base com coordenada conhecida (`--fixa` em
`rtk_base.py`) ou um serviço de correção.

## A grade de 1,85 cm na figura

Os pontos caem numa grade regular. Não é ruído com estrutura: é a NMEA GGA, que
com 5 casas decimais de minuto quantiza a posição em **1,85 cm**. Para 10 cm dá
5 níveis; para os 5 cm originalmente planejados seriam menos de 3, e o teste
nasceria com erro de quantização grande só por causa do formato.

`rtk_base.py --highprec` liga `CFG-NMEA-HIGHPREC`, que leva a GGA a 7 casas de
minuto — **0,185 mm**, cem vezes melhor. Trabalho de centímetro deve usá-lo
sempre. O parser do curso (`nmea.py`) já lê os dois formatos.
