"""
Script de Higienizacao Retroativa do Banco de Dados
Atualiza registros de contas onde days_active > 0 e is_valid == False para is_valid = True.
"""
import sys
from datetime import datetime

# Suporte a caracteres UTF-8 no terminal Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from server import SessionLocal, AccountHistory, Base, db_engine, ensure_schema_migrations

def cleanup_active_accounts():
    print("=" * 65)
    print("🧹 INICIANDO HIGIENIZAÇÃO RETROATIVA DO BANCO DE DADOS")
    print("=" * 65)

    # Garante migrações
    ensure_schema_migrations()

    session = SessionLocal()
    try:
        # Busca registros com dias ativos mas marcados como inválidos
        invalid_active_accounts = session.query(AccountHistory).filter(
            AccountHistory.days_active > 0,
            AccountHistory.is_valid == False
        ).all()

        total_found = len(invalid_active_accounts)
        print(f"📊 Registros identificados para correção: {total_found}")

        if total_found == 0:
            print("✨ Nenhuma inconsistência encontrada! Todas as contas com dias ativos já estão válidas.")
            print("=" * 65)
            return 0

        print("-" * 65)
        for idx, acc in enumerate(invalid_active_accounts, start=1):
            old_status = acc.status_message or "Sem status"
            new_status = f"⭐ {acc.days_active} DIAS (Ativa - Corrigida via Script)"
            
            acc.is_valid = True
            acc.status_message = new_status
            
            print(f"  [{idx}/{total_found}] MAC: {acc.mac} | ID: {acc.account_id or '-'} | Dias: {acc.days_active}")
            print(f"      De:   {old_status}")
            print(f"      Para: {new_status}")

        session.commit()
        print("-" * 65)
        print(f"✅ SUCESSO: {total_found} registro(s) atualizado(s) com is_valid=True e status de Ativa!")
        print("=" * 65)
        return total_found

    except Exception as e:
        session.rollback()
        print(f"❌ ERRO durante a higienização: {str(e)}")
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    cleanup_active_accounts()
