# 🧴 Sistema Essence — Gestão de Perfumes

Sistema simples para você controlar seus **perfumes, clientes, vendas, lucros e metas**.
Funciona **no seu computador, offline**, sem precisar de internet, sem login e sem mensalidade.
Seus dados ficam guardados de forma permanente no próprio computador.

---

## ✅ O que o sistema faz

- **Dashboard**: faturamento do mês, lucro, meta com barra de progresso, total investido no estoque e débitos em aberto.
- **Perfumes**: cadastrar, editar e apagar. O **lucro e a margem são calculados automaticamente**. O **estoque baixa sozinho** a cada venda.
- **Clientes / Vendas**: cada ficha pode ter **vários perfumes** (com datas diferentes) e **vários pagamentos**. O sistema mostra **Total, Pago e Saldo devedor** automaticamente.
- **Relatório do cliente**: botão 📄 em cada ficha gera o texto pronto para **copiar e colar no WhatsApp**.
- **Inadimplência**: lista quem tem **saldo devedor** com prazo vencido, até quitar.
- **Lixeira**: tudo que você apaga (perfume ou venda) pode ser **restaurado por 7 dias**.
- **Relatório PDF**: baixe um PDF com todos os clientes, perfumes, datas de compra e de pagamento.
- **Configurações**: definir a **meta do mês**, **fazer backup** e **restaurar** os dados.

---

## 💻 Como instalar (só na primeira vez)

O sistema precisa do **Python** instalado. Você só faz isso uma vez.

### Windows
1. Acesse **https://www.python.org/downloads/**
2. Clique em **Download Python** e abra o instalador.
3. **MUITO IMPORTANTE:** na primeira tela, marque a caixinha **“Add Python to PATH”** e depois clique em **Install Now**.
4. Aguarde terminar e feche.

### Mac
- O Mac normalmente já vem com Python. Se não tiver, baixe em **https://www.python.org/downloads/** e instale.

---

## ▶️ Como abrir o sistema no dia a dia

### Windows
- Dê **dois cliques** no arquivo **`iniciar.bat`**.
- Uma janela preta vai abrir e, em poucos segundos, o sistema abre **sozinho no navegador**.
- Na primeira vez ele demora um pouco mais (está se preparando). Depois é rápido.

### Mac / Linux
- Abra o **Terminal** na pasta do sistema e digite:
  ```
  ./iniciar.sh
  ```
- O navegador abre sozinho em poucos segundos.

> Se o navegador não abrir sozinho, digite este endereço no navegador:
> **http://127.0.0.1:8000**

### Para fechar o sistema
- **Windows:** feche a janela preta.
- **Mac/Linux:** aperte **Ctrl + C** no Terminal.

---

## 💾 Backup (cópia de segurança) — importante!

Como são dados financeiros, faça backup de vez em quando:

1. No menu lateral, clique em **Configurações**.
2. Clique em **“Baixar backup agora”** — um arquivo `.db` vai para a sua pasta de Downloads.
3. Guarde esse arquivo em um lugar seguro (pendrive, e-mail ou nuvem).

### Restaurar um backup
1. Em **Configurações**, na seção **Restaurar dados**, selecione o arquivo de backup `.db`.
2. Clique em **“Restaurar do arquivo”** e confirme.
3. Antes de substituir, o sistema cria automaticamente uma cópia de segurança dos dados atuais na pasta `backups/`.

---

## 🗑️ Lixeira (apagar sem medo)

Quando você apaga um perfume ou uma venda, ele **não some na hora**: vai para a **Lixeira**.
- Você tem **7 dias** para restaurar (botão **"↩️ Restaurar"**).
- Depois desse prazo, o sistema apaga sozinho, de vez.
- Pode também **excluir de vez** na hora ou **esvaziar a lixeira**, se quiser.

## 🛒 Ficha do cliente (vários perfumes e pagamentos)

Cada cliente tem uma **ficha** que pode conter **vários perfumes**, comprados até em **datas diferentes**:
1. Clique em **＋ Nova ficha**.
2. Adicione os perfumes em **“Perfumes da compra”** (perfume, quantidade, valor e a data de cada um).
3. Se for **Prazo**, registre os **pagamentos** conforme o cliente vai pagando, em **“Pagamentos recebidos”**.
4. O sistema mostra sozinho **Total**, **Pago** e **Saldo devedor**. Quando o saldo chega a **R$ 0,00**, a ficha vira **Quitada** e sai da inadimplência.

> O **estoque baixa automaticamente** quando você vende (ex.: 6 Delina → vendeu 1 → fica 5). Não dá para vender mais do que há em estoque. Se apagar ou editar a ficha, o estoque é devolvido/corrigido.

Para receber um pagamento rápido, use o botão 💵 na linha do cliente.

## 📄 Relatórios

- **Relatório do cliente (WhatsApp):** botão 📄 em cada ficha → abre o texto pronto, com botão **Copiar texto**. O rodapé (chave Pix, nome e empresa) vem das **Configurações** e você pode editar quando quiser.
- **Relatório geral em PDF:** botão **“Relatório geral”** (ou em Configurações) → baixa um PDF com todos os clientes, perfumes, valores e datas.

> Dica sobre **inadimplência**: um cliente aparece lá quando tem **saldo devedor** (ainda deve) **e** o vencimento já passou. Ao quitar o saldo, ele sai da lista automaticamente.

## 📂 Onde ficam as coisas importantes

| O quê | Onde |
|---|---|
| **Banco de dados (seus dados)** | arquivo **`essence.db`** na pasta do sistema |
| **Backups e cópias automáticas** | pasta **`backups/`** |
| **Logo** | **`assets/logo.png`** (troque por sua logo, mantendo o mesmo nome) |

> 👉 Para um backup manual rápido, basta **copiar o arquivo `essence.db`** para outro lugar.
> Ele é criado automaticamente na primeira vez que você abre o sistema.

---

## 🖼️ Trocar a logo

Coloque a sua logo dentro da pasta **`assets/`** com o nome **`logo.png`** (substituindo a que já existe).
Se o arquivo não existir, o sistema mostra um “E” laranja no lugar — o layout não quebra.

---

## ℹ️ Dados de exemplo

Na primeira execução o sistema já vem com **perfumes e vendas de exemplo** (inclusive clientes em atraso),
para você testar todas as telas. Pode apagar tudo quando quiser e cadastrar os seus.

---

## 🧮 Como as contas são feitas

- **Lucro do perfume** = valor de venda − preço de custo
- **Margem (%)** = lucro ÷ valor de venda × 100
- **Faturamento do mês** = soma das vendas do mês atual
- **Lucro do mês** = soma dos lucros das vendas do mês atual
- **Total investido** = soma de (preço de custo × estoque) de todos os perfumes
- **Falta para a meta** = meta − faturamento do mês (se atingiu, mostra “Meta atingida! 🎉”)
- **Inadimplente** = venda Pendente cuja data de pagamento já passou

---

## ❓ Problemas comuns

- **“Python não encontrado”** → instale o Python (passo acima) e, no Windows, lembre de marcar **“Add Python to PATH”**.
- **A página não abre** → digite **http://127.0.0.1:8000** no navegador.
- **Perdi meus dados** → restaure pelo backup mais recente em **Configurações → Restaurar dados**.

Pronto! É só usar. 💛
