# Capturas de afirmação retratada

**Não usar para gerar material.** Ficam aqui porque a medida existiu e alguém
pode querer verificar a retratação — não porque o resultado valha.

## `glo_com_bloco5.nmea` e `glo_sem_bloco6.nmea`

Dois blocos de um teste A/B que **afirmava que ligar o GLONASS melhora a
dispersão em 2,6×**. Não melhora.

O confundidor: o SBAS entrava e saía sozinho, em proporções muito diferentes
entre os blocos — 139, 213, 152 e 65 épocas em DGPS nos quatro blocos da série.
Era ele, e não o GLONASS, que produzia a diferença. Filtrando só épocas
autônomas, sobrava 1,17× com os grupos se sobrepondo.

A campanha controlada que substituiu isto está em `../matriz/`: SBAS desligado
do começo ao fim, ordem das condições girada, três rodadas, blocos de duração
igual. Ela confirmou **nenhum efeito mensurável do GLONASS na dispersão**.

O GLONASS faz outra coisa, e essa se sustenta: ele decide se o RTK **fixa**. Com
ele, 306 épocas fixas em 901; sem ele, **0 em 600**. Efeito categórico, que o CEP
não mostra — e por isso ficou invisível enquanto só se olhava dispersão.

## A lição de método

Um A/B só mede o que se quer se **tudo que não é a variável estiver congelado**.
O SBAS não estava, e ele tem autonomia para entrar e sair conforme a geometria.
Desde então, comparativo de constelação roda com `CFG-SIGNAL-SBAS_ENA` = 0 do
começo ao fim, e a proporção de qualidades por bloco vai no relatório para que
esse tipo de contaminação apareça.
