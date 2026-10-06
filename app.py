import os
import sqlite3
from functools import wraps

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "shopping.db")

app = Flask(__name__)

# 本番環境では環境変数から設定してください
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "development-secret-key-change-this"
)


# ============================================================
# データベース
# ============================================================

def get_db():
    """現在のリクエストで使用するDB接続を取得する。"""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row

    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    """リクエスト終了時にDB接続を閉じる。"""
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_db():
    """DB・テーブル・初期データを作成する。"""
    db = sqlite3.connect(DATABASE)

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            account_name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            genre TEXT NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            image_url TEXT,
            description TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS purchase_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            purchased_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        """
    )

    # --------------------------------------------------------
    # サンプルユーザー
    # --------------------------------------------------------
    user_count = db.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    if user_count == 0:
        db.execute(
            """
            INSERT INTO users (
                email,
                password,
                account_name
            )
            VALUES (?, ?, ?)
            """,
            (
                "user@example.com",
                generate_password_hash("password"),
                "山田 太郎",
            ),
        )

    # --------------------------------------------------------
    # サンプル商品
    # --------------------------------------------------------
    product_count = db.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]

    if product_count == 0:
        products = [
            (
                "ワイヤレスイヤホン",
                12800,
                "家電",
                10,
                "https://placehold.co/600x400?text=Wireless+Earphones",
                "高音質で使いやすいワイヤレスイヤホンです。通勤・通学にもおすすめです。",
            ),
            (
                "スマートウォッチ",
                19800,
                "家電",
                5,
                "https://placehold.co/600x400?text=Smart+Watch",
                "健康管理や通知確認ができる便利なスマートウォッチです。",
            ),
            (
                "デザインTシャツ",
                3980,
                "ファッション",
                20,
                "https://placehold.co/600x400?text=T-Shirt",
                "シンプルで着回しやすいデザインのTシャツです。",
            ),
            (
                "レザーバッグ",
                15800,
                "ファッション",
                3,
                "https://placehold.co/600x400?text=Leather+Bag",
                "上質なレザーを使用したシンプルなバッグです。",
            ),
            (
                "コーヒーカップ",
                1800,
                "生活雑貨",
                15,
                "https://placehold.co/600x400?text=Coffee+Cup",
                "毎日のコーヒータイムにぴったりのコーヒーカップです。",
            ),
            (
                "デスクライト",
                4980,
                "生活雑貨",
                0,
                "https://placehold.co/600x400?text=Desk+Light",
                "明るさを調整できるデスクライトです。",
            ),
            (
                "小説「未来への旅」",
                1200,
                "書籍",
                8,
                "https://placehold.co/600x400?text=Book",
                "未来の世界を舞台にした人気小説です。",
            ),
            (
                "Python入門",
                2980,
                "書籍",
                12,
                "https://placehold.co/600x400?text=Python+Book",
                "Pythonプログラミングを基礎から学べる入門書です。",
            ),
        ]

        db.executemany(
            """
            INSERT INTO products (
                name,
                price,
                genre,
                stock,
                image_url,
                description
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            products,
        )

    db.commit()
    db.close()


# ============================================================
# 認証
# ============================================================

def login_required(view):
    """ログイン必須ページ用デコレーター。"""

    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("この操作を行うにはログインが必要です。", "warning")
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped_view


@app.context_processor
def inject_current_user():
    """テンプレートからログイン状態を参照できるようにする。"""

    user = None

    if "user_id" in session:
        db = get_db()

        user = db.execute(
            """
            SELECT id, email, account_name
            FROM users
            WHERE id = ?
            """,
            (session["user_id"],),
        ).fetchone()

    return {
        "current_user": user
    }


# ============================================================
# トップ画面
# ============================================================

@app.route("/")
def index():
    """
    商品一覧を表示する。

    genre が指定されている場合は、
    指定されたジャンルの商品だけを表示する。
    """

    db = get_db()

    genre = request.args.get("genre", "").strip()

    if genre:
        products = db.execute(
            """
            SELECT *
            FROM products
            WHERE genre = ?
            ORDER BY id
            """,
            (genre,),
        ).fetchall()
    else:
        products = db.execute(
            """
            SELECT *
            FROM products
            ORDER BY id
            """
        ).fetchall()

    genres = db.execute(
        """
        SELECT DISTINCT genre
        FROM products
        ORDER BY genre
        """
    ).fetchall()

    return render_template(
        "index.html",
        products=products,
        genres=genres,
        selected_genre=genre,
    )


# ============================================================
# ログイン
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    """メールアドレスとパスワードによるログイン。"""

    # すでにログイン済みならトップへ
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # 入力チェック
        if not email or not password:
            flash(
                "メールアドレスとパスワードを入力してください。",
                "danger",
            )
            return render_template("login.html")

        db = get_db()

        user = db.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()

        # メールアドレス・パスワードの照合
        if user is None or not check_password_hash(
            user["password"],
            password,
        ):
            flash(
                "メールアドレスまたはパスワードが一致しません。",
                "danger",
            )
            return render_template("login.html")

        # セッションを作成
        session.clear()
        session["user_id"] = user["id"]

        flash(
            f"{user['account_name']}さん、ログインしました。",
            "success",
        )

        return redirect(url_for("index"))

    return render_template("login.html")


# ============================================================
# ログアウト
# ============================================================

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    """ログイン状態を解除する。"""

    session.clear()

    flash(
        "ログアウトしました。",
        "success",
    )

    return redirect(url_for("index"))


# ============================================================
# 商品詳細
# ============================================================

@app.route("/products/<int:product_id>")
def product_detail(product_id):
    """商品の詳細情報を表示する。"""

    db = get_db()

    product = db.execute(
        """
        SELECT *
        FROM products
        WHERE id = ?
        """,
        (product_id,),
    ).fetchone()

    if product is None:
        flash(
            "指定された商品が見つかりません。",
            "danger",
        )
        return redirect(url_for("index"))

    # カートに入れられる状態か
    can_add_to_cart = (
        "user_id" in session
        and product["stock"] > 0
    )

    return render_template(
        "product_detail.html",
        product=product,
        can_add_to_cart=can_add_to_cart,
    )


# ============================================================
# カート
# ============================================================

@app.route("/cart/add/<int:product_id>", methods=["POST"])
@login_required
def add_to_cart(product_id):
    """
    指定した数量の商品をカートに追加する。
    """

    db = get_db()

    product = db.execute(
        """
        SELECT *
        FROM products
        WHERE id = ?
        """,
        (product_id,),
    ).fetchone()

    if product is None:
        flash(
            "商品が見つかりません。",
            "danger",
        )
        return redirect(url_for("index"))

    if product["stock"] <= 0:
        flash(
            "この商品は在庫切れです。",
            "danger",
        )
        return redirect(
            url_for(
                "product_detail",
                product_id=product_id,
            )
        )

    # フォームから数量を取得
    try:
        quantity = int(request.form.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1

    # 数量チェック
    if quantity < 1:
        flash(
            "数量は1個以上を指定してください。",
            "danger",
        )
        return redirect(
            url_for(
                "product_detail",
                product_id=product_id,
            )
        )

    # セッション上のカート
    cart = session.get("cart", {})

    product_key = str(product_id)

    current_quantity = int(
        cart.get(product_key, 0)
    )

    new_quantity = current_quantity + quantity

    # 在庫数を超えないようにする
    if new_quantity > product["stock"]:
        flash(
            f"在庫は{product['stock']}個です。"
            f"カートには最大{product['stock']}個まで追加できます。",
            "warning",
        )
        return redirect(
            url_for(
                "product_detail",
                product_id=product_id,
            )
        )

    cart[product_key] = new_quantity

    session["cart"] = cart
    session.modified = True

    flash(
        f"「{product['name']}」を{quantity}個カートに追加しました。",
        "success",
    )

    return redirect(
        url_for(
            "product_detail",
            product_id=product_id,
        )
    )

@app.route("/cart")
@login_required
def cart():
    """カート内の商品一覧と合計金額を表示する。"""

    db = get_db()

    cart_data = session.get("cart", {})

    items = []
    total_amount = 0

    for product_id, quantity in cart_data.items():

        product = db.execute(
            """
            SELECT *
            FROM products
            WHERE id = ?
            """,
            (int(product_id),),
        ).fetchone()

        if product is None:
            continue

        quantity = int(quantity)

        subtotal = product["price"] * quantity

        items.append(
            {
                "product": product,
                "quantity": quantity,
                "subtotal": subtotal,
            }
        )

        total_amount += subtotal

    return render_template(
        "cart.html",
        items=items,
        total_amount=total_amount,
    )


@app.route("/purchase/confirm")
@login_required
def purchase_confirm():
    """購入確認画面を表示する。"""

    db = get_db()

    cart_data = session.get("cart", {})

    if not cart_data:
        flash(
            "カートに商品がありません。",
            "warning",
        )
        return redirect(url_for("cart"))

    items = []
    total_amount = 0

    for product_id, quantity in cart_data.items():

        product = db.execute(
            """
            SELECT *
            FROM products
            WHERE id = ?
            """,
            (int(product_id),),
        ).fetchone()

        if product is None:
            continue

        quantity = int(quantity)

        # 最新在庫を確認
        if quantity > product["stock"]:
            flash(
                f"「{product['name']}」の在庫が不足しています。",
                "danger",
            )
            return redirect(url_for("cart"))

        subtotal = product["price"] * quantity

        items.append(
            {
                "product": product,
                "quantity": quantity,
                "subtotal": subtotal,
            }
        )

        total_amount += subtotal

    if not items:
        flash(
            "カートに商品がありません。",
            "warning",
        )
        return redirect(url_for("cart"))

    return render_template(
        "purchase_confirm.html",
        items=items,
        total_amount=total_amount,
    )

@app.route("/purchase/complete", methods=["POST"])
@login_required
def purchase_complete():
    """
    購入を確定する。

    購入履歴を登録し、商品の在庫を減らし、
    カートを空にする。
    """

    db = get_db()

    cart_data = session.get("cart", {})

    if not cart_data:
        flash(
            "カートに商品がありません。",
            "warning",
        )
        return redirect(url_for("cart"))

    user_id = session["user_id"]

    try:
        # トランザクション開始
        db.execute("BEGIN")

        for product_id, quantity in cart_data.items():

            product = db.execute(
                """
                SELECT *
                FROM products
                WHERE id = ?
                """,
                (int(product_id),),
            ).fetchone()

            if product is None:
                raise ValueError(
                    "購入対象の商品が見つかりません。"
                )

            quantity = int(quantity)

            # 在庫確認
            if quantity <= 0:
                raise ValueError(
                    "購入数量が不正です。"
                )

            if product["stock"] < quantity:
                raise ValueError(
                    f"「{product['name']}」の在庫が不足しています。"
                )

            amount = product["price"] * quantity

            # 購入履歴を登録
            db.execute(
                """
                INSERT INTO purchase_history (
                    user_id,
                    product_id,
                    product_name,
                    quantity,
                    amount
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    product["id"],
                    product["name"],
                    quantity,
                    amount,
                ),
            )

            # 在庫を減らす
            db.execute(
                """
                UPDATE products
                SET stock = stock - ?
                WHERE id = ?
                """,
                (
                    quantity,
                    product["id"],
                ),
            )

        # DBへ確定
        db.commit()

    except Exception as e:
        db.rollback()

        flash(
            str(e),
            "danger",
        )

        return redirect(url_for("cart"))

    # 購入完了後にカートを空にする
    session.pop("cart", None)
    session.modified = True

    return render_template(
        "purchase_complete.html"
    )

@app.route("/purchase/history")
@login_required
def purchase_history():
    """ログインユーザーの購入履歴を表示する。"""

    db = get_db()

    history = db.execute(
        """
        SELECT
            id,
            product_name,
            quantity,
            amount,
            purchased_at
        FROM purchase_history
        WHERE user_id = ?
        ORDER BY purchased_at DESC, id DESC
        """,
        (session["user_id"],),
    ).fetchall()

    return render_template(
        "purchase_history.html",
        history=history,
    )



# ============================================================
# 起動
# ============================================================

if __name__ == "__main__":
    # DBが存在しない場合も含め、テーブル・初期データを作成
    with app.app_context():
        init_db()

    print("=" * 60)
    print("通販システムを起動します")
    print("URL: http://127.0.0.1:5000/")
    print("")
    print("テストユーザー")
    print("メールアドレス: user@example.com")
    print("パスワード      : password")
    print("=" * 60)

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )
