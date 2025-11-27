import json
import sqlite3


class Database:
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._ensure_schema()

    def _ensure_schema(self):
        # payments table to store every payment attempt and provider/admin payloads
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                method TEXT NOT NULL,
                plan TEXT,
                amount REAL,
                status TEXT NOT NULL,
                provider_invoice_id TEXT,
                pay_url TEXT,
                wallet_address TEXT,
                tx_hash TEXT,
                tx_from TEXT,
                tx_to TEXT,
                tx_value REAL,
                tx_timestamp DATETIME,
                user_name TEXT,
                first_name TEXT,
                admin_id INTEGER,
                admin_name TEXT,
                old_subscription_end DATETIME,
                new_subscription_end DATETIME,
                payload TEXT,
                description TEXT,
                raw_response TEXT,
                paid_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        existing_cols = {row["name"] for row in self.cursor.execute("PRAGMA table_info(payments)")}
        for col, ddl in [
            ("user_name", "ALTER TABLE payments ADD COLUMN user_name TEXT"),
            ("first_name", "ALTER TABLE payments ADD COLUMN first_name TEXT"),
            ("admin_id", "ALTER TABLE payments ADD COLUMN admin_id INTEGER"),
            ("admin_name", "ALTER TABLE payments ADD COLUMN admin_name TEXT"),
            ("old_subscription_end", "ALTER TABLE payments ADD COLUMN old_subscription_end DATETIME"),
            ("new_subscription_end", "ALTER TABLE payments ADD COLUMN new_subscription_end DATETIME"),
        ]:
            if col not in existing_cols:
                self.cursor.execute(ddl)

        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(telegram_id);"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);"
        )
        self.conn.commit()

    @staticmethod
    def _jsonify(value):
        if value is None:
            return None
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)

    def create_payment_entry(
        self,
        *,
        telegram_id,
        method,
        amount,
        plan=None,
        status="pending",
        provider_invoice_id=None,
        pay_url=None,
        wallet_address=None,
        user_name=None,
        first_name=None,
        admin_id=None,
        admin_name=None,
        old_subscription_end=None,
        new_subscription_end=None,
        payload=None,
        description=None,
        raw_response=None,
    ):
        raw = self._jsonify(raw_response)
        self.cursor.execute(
            """
            INSERT INTO payments (
                telegram_id,
                method,
                amount,
                plan,
                status,
                provider_invoice_id,
                pay_url,
                wallet_address,
                user_name,
                first_name,
                admin_id,
                admin_name,
                old_subscription_end,
                new_subscription_end,
                payload,
                description,
                raw_response
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                telegram_id,
                method,
                amount,
                plan,
                status,
                provider_invoice_id,
                pay_url,
                wallet_address,
                user_name,
                first_name,
                admin_id,
                admin_name,
                old_subscription_end,
                new_subscription_end,
                payload,
                description,
                raw,
            ),
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def update_payment_entry(
        self,
        payment_id,
        *,
        status=None,
        provider_invoice_id=None,
        pay_url=None,
        wallet_address=None,
        tx_hash=None,
        tx_from=None,
        tx_to=None,
        tx_value=None,
        tx_timestamp=None,
        user_name=None,
        first_name=None,
        admin_id=None,
        admin_name=None,
        old_subscription_end=None,
        new_subscription_end=None,
        payload=None,
        description=None,
        paid_at=None,
        raw_response=None,
    ):
        fields = []
        params = []
        if status is not None:
            fields.append("status = ?")
            params.append(status)
        if provider_invoice_id is not None:
            fields.append("provider_invoice_id = ?")
            params.append(provider_invoice_id)
        if pay_url is not None:
            fields.append("pay_url = ?")
            params.append(pay_url)
        if wallet_address is not None:
            fields.append("wallet_address = ?")
            params.append(wallet_address)
        if user_name is not None:
            fields.append("user_name = ?")
            params.append(user_name)
        if first_name is not None:
            fields.append("first_name = ?")
            params.append(first_name)
        if admin_id is not None:
            fields.append("admin_id = ?")
            params.append(admin_id)
        if admin_name is not None:
            fields.append("admin_name = ?")
            params.append(admin_name)
        if old_subscription_end is not None:
            fields.append("old_subscription_end = ?")
            params.append(old_subscription_end)
        if new_subscription_end is not None:
            fields.append("new_subscription_end = ?")
            params.append(new_subscription_end)
        if tx_hash is not None:
            fields.append("tx_hash = ?")
            params.append(tx_hash)
        if tx_from is not None:
            fields.append("tx_from = ?")
            params.append(tx_from)
        if tx_to is not None:
            fields.append("tx_to = ?")
            params.append(tx_to)
        if tx_value is not None:
            fields.append("tx_value = ?")
            params.append(tx_value)
        if tx_timestamp is not None:
            fields.append("tx_timestamp = ?")
            params.append(tx_timestamp)
        if payload is not None:
            fields.append("payload = ?")
            params.append(payload)
        if description is not None:
            fields.append("description = ?")
            params.append(description)
        if paid_at is not None:
            fields.append("paid_at = ?")
            params.append(paid_at)
        if raw_response is not None:
            fields.append("raw_response = ?")
            params.append(self._jsonify(raw_response))

        # always bump updated_at to see last change moment
        fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(payment_id)

        query = f"UPDATE payments SET {', '.join(fields)} WHERE id = ?"
        self.cursor.execute(query, params)
        self.conn.commit()

    def add_user(self, tg_id):
        self.cursor.execute(
            "INSERT INTO users (telegram_id) VALUES (?)",
            (tg_id,)
        )
        self.conn.commit()

    def get_setting(self, key):
        self.cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = self.cursor.fetchone()
        if row:
            return row["value"]
        return None

    def edit_setting(self, key, new_value):
        self.cursor.execute(
            "UPDATE settings SET value = ? WHERE key = ?",
            (new_value, key)
        )
        self.conn.commit()


    def update_user_field(self, telegram_id, column, value):
        query = f"UPDATE users SET {column} = ? WHERE telegram_id = ?"
        self.cursor.execute(query, (value, telegram_id))
        self.conn.commit()

    def add_subscription_plan(self, telegram_id, new_plan):
        self.cursor.execute(
            "SELECT subscription_plan FROM users WHERE telegram_id = ?",
            (telegram_id,)
        )
        row = self.cursor.fetchone()
        current = json.loads(row["subscription_plan"] or "[]")

        if new_plan not in current:
            current.append(new_plan)

        self.cursor.execute(
            "UPDATE users SET subscription_plan = ? WHERE telegram_id = ?",
            (json.dumps(current), telegram_id)
        )
        self.conn.commit()

    def remove_subscription_plan(self, telegram_id, plan_to_remove):
        self.cursor.execute(
            "SELECT subscription_plan FROM users WHERE telegram_id = ?",
            (telegram_id,)
        )
        row = self.cursor.fetchone()
        current = json.loads(row["subscription_plan"] or "[]")

        updated = [plan for plan in current if plan != plan_to_remove]

        self.cursor.execute(
            "UPDATE users SET subscription_plan = ? WHERE telegram_id = ?",
            (json.dumps(updated), telegram_id)
        )
        self.conn.commit()

    def get_user_plans(self, telegram_id):
        self.cursor.execute(
            "SELECT subscription_plan FROM users WHERE telegram_id = ?",
            (telegram_id,)
        )
        row = self.cursor.fetchone()
        if row:
            return json.loads(row["subscription_plan"] or "[]")
        return []

    def get_user(self, tg_id):
        query = "SELECT * FROM users WHERE telegram_id = ?;"
        self.cursor.execute(query, (tg_id,))
        result = self.cursor.fetchone()
        return dict(result) if result else None

    def get_users_by_job_title(self, job_title):
        query = "SELECT * FROM users WHERE job_title = ?;"
        self.cursor.execute(query, (job_title,))
        return [dict(row) for row in self.cursor.fetchall()]

    def add_channel(self, name, channel_id):
        self.cursor.execute("SELECT value FROM settings WHERE key = 'channel'")
        row = self.cursor.fetchone()

        channels = []
        if row:
            channels = json.loads(row['value'])

        channels.append({'name': name, 'id': channel_id})
        json_value = json.dumps(channels)

        self.cursor.execute("""
            INSERT INTO settings (key, value)
            VALUES ('channel', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (json_value,))
        self.conn.commit()

    def remove_channel_by_id(self, channel_id):
        self.cursor.execute("SELECT value FROM settings WHERE key = 'channel'")
        row = self.cursor.fetchone()

        if not row:
            return

        channels = json.loads(row['value'])
        filtered = [ch for ch in channels if ch['id'] != channel_id]
        json_value = json.dumps(filtered)

        self.cursor.execute("""
            UPDATE settings SET value = ?
            WHERE key = 'channel'
        """, (json_value,))
        self.conn.commit()

    def get_channels(self):
        self.cursor.execute("SELECT value FROM settings WHERE key = 'channel'")
        row = self.cursor.fetchone()
        if row:
            try:
                return json.loads(row['value'])
            except json.JSONDecodeError:
                return []
        return []
    
    def get_free_crypto_address(self):
        self.cursor.execute("SELECT value FROM settings WHERE key = 'crypto_address'")
        row = self.cursor.fetchone()
        addresses = json.loads(row["value"])

        for item in addresses:
            if not item["used"]:
                return item["address"]
        return None

    def mark_address_as_used(self, address_to_mark):
        self.cursor.execute("SELECT value FROM settings WHERE key = 'crypto_address'")
        row = self.cursor.fetchone()
        addresses = json.loads(row["value"])

        for item in addresses:
            if item["address"] == address_to_mark:
                item["used"] = True
                break

        self.cursor.execute(
            "UPDATE settings SET value = ? WHERE key = 'crypto_address'",
            (json.dumps(addresses),)
        )
        self.conn.commit()

    def unmark_address_as_used(self, address_to_unmark):
        self.cursor.execute("SELECT value FROM settings WHERE key = 'crypto_address'")
        row = self.cursor.fetchone()
        if not row:
            return

        addresses = json.loads(row["value"])

        for item in addresses:
            if item["address"] == address_to_unmark:
                item["used"] = False
                break

        self.cursor.execute(
            "UPDATE settings SET value = ? WHERE key = 'crypto_address'",
            (json.dumps(addresses),)
        )
        self.conn.commit()

    def close(self):
        self.cursor.close()
        self.conn.close()
