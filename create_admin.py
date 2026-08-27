"""
Utilitario para Criacao e Gerenciamento do Primeiro Usuario Administrador (SaaS)
Uso via terminal:
  python create_admin.py --username admin --password secret
  python create_admin.py -u admin -p secret
  python create_admin.py
"""

import sys
import argparse
from getpass import getpass

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from server import SessionLocal, User, hash_password, Base, db_engine


def create_or_update_admin(username: str, password: str) -> User:
    """Cria ou atualiza um usuario com role='admin' e senha com hash bcrypt."""
    Base.metadata.create_all(bind=db_engine)
    session = SessionLocal()
    try:
        username_clean = username.strip()
        if not username_clean:
            raise ValueError("Nome de usuario nao pode ser vazio.")
        if not password:
            raise ValueError("A senha nao pode ser vazia.")

        user = session.query(User).filter(User.username == username_clean).first()
        hashed = hash_password(password)

        if user:
            user.password_hash = hashed
            user.role = "admin"
            session.commit()
            session.refresh(user)
            print(f"✅ Usuario administrador '{username_clean}' atualizado com sucesso! (ID: {user.id})")
        else:
            user = User(
                username=username_clean,
                password_hash=hashed,
                role="admin"
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            print(f"✅ Usuario administrador '{username_clean}' criado com sucesso! (ID: {user.id})")
        return user
    except Exception as e:
        session.rollback()
        print(f"❌ Erro ao registrar administrador: {e}")
        sys.exit(1)
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Criar ou atualizar usuario Admin no Gerador IPTV SaaS")
    parser.add_argument("--username", "-u", default=None, help="Nome de usuario do admin (padrao: admin)")
    parser.add_argument("--password", "-p", default=None, help="Senha do admin")
    args = parser.parse_args()

    username = args.username
    password = args.password

    if not username:
        if sys.stdin.isatty():
            username = input("Digite o nome de usuario do Admin [admin]: ").strip() or "admin"
        else:
            username = "admin"

    if not password:
        if sys.stdin.isatty():
            password = getpass(f"Digite a senha para o usuario '{username}': ").strip()
        else:
            password = "admin"

    if not password:
        print("❌ Senha nao pode ser vazia.")
        sys.exit(1)

    create_or_update_admin(username, password)


if __name__ == "__main__":
    main()
