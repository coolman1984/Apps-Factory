"""Bilingual error catalogue for af-atrest vendor recovery, escrow, migration, and off-site backup."""

from __future__ import annotations

CATALOGUE: dict[str, dict[str, str]] = {
    'ATREST_OK': {
        'en': 'OK',
        'ar': 'تم بنجاح',
    },
    'ATREST_RECOVERED_PACKAGE_BAD_FORMAT': {
        'en': 'This is not a valid vendor recovered-key package.',
        'ar': 'هذه ليست حزمة استعادة مفتاح صالحة من المورّد.',
    },
    'ATREST_RECOVERED_PACKAGE_TAMPERED': {
        'en': 'The recovered-key package does not match this device or was changed.',
        'ar': 'حزمة الاستعادة لا تطابق هذا الجهاز أو تم تعديلها.',
    },
    'ATREST_RECOVERED_KEY_CONFLICT': {
        'en': 'This device already has a different data key and non-empty databases. Remove local data or use an empty data directory before restore.',
        'ar': 'هذا الجهاز يحتوي بالفعل على مفتاح بيانات مختلف وقواعد بيانات غير فارغة. احذف البيانات المحلية أو استخدم مجلد بيانات فارغًا قبل الاستعادة.',
    },
    'ATREST_DEVICE_TRANSFER_KEY_BAD': {
        'en': 'The device transfer key on this machine is missing or invalid.',
        'ar': 'مفتاح نقل الجهاز على هذا الحاسوب مفقود أو غير صالح.',
    },
    'ATREST_BACKUP_MISMATCH': {
        'en': 'The backup does not match this recovery key. Use the backup taken with the same data directory.',
        'ar': 'النسخة الاحتياطية لا تطابق مفتاح الاستعادة. استخدم النسخة الاحتياطية من نفس مجلد البيانات.',
    },
    'ATREST_BACKUP_NOT_ENCRYPTED': {
        'en': 'The backup file is not an encrypted af-atrest archive.',
        'ar': 'ملف النسخة الاحتياطية ليس أرشيفًا مشفرًا من af-atrest.',
    },
    'ATREST_BACKUP_AUTH_FAILED': {
        'en': 'The backup could not be decrypted with this key (authentication failed).',
        'ar': 'تعذّر فك تشفير النسخة الاحتياطية بهذا المفتاح (فشل التحقق).',
    },
    'ATREST_ESCROW_BAD_PUBLIC_KEY': {
        'en': 'The vendor escrow public key is invalid.',
        'ar': 'مفتاح الضمان العام للمورّد غير صالح.',
    },
    'ATREST_ESCROW_SEAL_FAILED': {
        'en': 'Could not seal the data key for escrow.',
        'ar': 'تعذّر إغلاق مفتاح البيانات للضمان.',
    },
    'ATREST_ESCROW_UPLOAD_FAILED': {
        'en': 'Upload to the escrow service failed.',
        'ar': 'فشل الرفع إلى خدمة الضمان.',
    },
    'ATREST_ESCROW_UPLOAD_REJECTED': {
        'en': 'The escrow service refused this package.',
        'ar': 'رفضت خدمة الضمان هذه الحزمة.',
    },
    'ATREST_OFFSITE_DISABLED': {
        'en': 'Daily off-site backup is turned off.',
        'ar': 'النسخ الاحتياطي اليومي خارج الموقع متوقف.',
    },
    'ATREST_OFFSITE_NOT_DUE': {
        'en': 'Off-site backup is not due yet today.',
        'ar': 'النسخ الاحتياطي خارج الموقع غير مستحق اليوم بعد.',
    },
    'ATREST_SYNC_STATE_BAD': {
        'en': 'The local sync state file is damaged.',
        'ar': 'ملف حالة المزامنة المحلي تالف.',
    },
    'ATREST_MIGRATE_ALREADY_ENCRYPTED': {
        'en': 'This data directory is already encrypted.',
        'ar': 'مجلد البيانات مشفّر بالفعل.',
    },
    'ATREST_MIGRATE_NO_PLAINTEXT_DB': {
        'en': 'No plaintext SQLite database was found to migrate.',
        'ar': 'لم يُعثر على قاعدة بيانات SQLite غير مشفّرة للترحيل.',
    },
    'ATREST_MIGRATE_SQLCIPHER_MISSING': {
        'en': 'sqlcipher3 is required to migrate to encrypted storage.',
        'ar': 'يلزم sqlcipher3 للترحيل إلى التخزين المشفّر.',
    },
    'ATREST_MIGRATE_VERIFY_FAILED': {
        'en': 'Migration verification failed; plaintext data was restored from the safety backup.',
        'ar': 'فشل التحقق بعد الترحيل؛ تمت استعادة البيانات غير المشفّرة من النسخة الاحتياطية الآمنة.',
    },
    'ATREST_MIGRATE_IN_PROGRESS': {
        'en': 'A previous migration left temporary files; clean up or run rollback first.',
        'ar': 'ترك ترحيل سابق ملفات مؤقتة؛ نظّف أو نفّذ التراجع أولًا.',
    },
    'ATREST_VAULT_WRONG_PASSWORD': {
        'en': 'The vault master password is wrong.',
        'ar': 'كلمة مرور الخزنة الرئيسية غير صحيحة.',
    },
    'ATREST_VAULT_TAMPERED': {
        'en': 'The vault database is damaged or was changed.',
        'ar': 'قاعدة بيانات الخزنة تالفة أو تم تعديلها.',
    },
    'ATREST_VAULT_NO_ESCROW_KEY': {
        'en': 'No escrow private key is loaded in the vault.',
        'ar': 'لا يوجد مفتاح ضمان خاص محمّل في الخزنة.',
    },
    'ATREST_VAULT_ESCROW_NOT_FOUND': {
        'en': 'No escrow record matches this company or device.',
        'ar': 'لا يوجد سجل ضمان يطابق هذا العميل أو الجهاز.',
    },
    'ATREST_VAULT_UNSEAL_FAILED': {
        'en': 'Could not decrypt the escrow package with the loaded private key.',
        'ar': 'تعذّر فك تشفير حزمة الضمان بالمفتاح الخاص المحمّل.',
    },
    'ATREST_VAULT_BAD_TARGET_KEY': {
        'en': 'The target device transfer public key is invalid.',
        'ar': 'مفتاح النقل العام للجهاز الهدف غير صالح.',
    },
}


class AtRestError(Exception):
    """Raised with a catalogue code; ``message(lang)`` returns localized text."""

    def __init__(self, code: str, detail: str | None = None):
        if code not in CATALOGUE:
            raise ValueError('unknown error code: ' + code)
        self.code = code
        self.detail = detail
        super().__init__(code)

    def message(self, lang: str = 'en') -> str:
        lang = 'ar' if lang and lang.lower().startswith('ar') else 'en'
        text = CATALOGUE[self.code][lang]
        if self.detail:
            return text + ' (' + self.detail + ')'
        return text


def all_codes() -> list[str]:
    return sorted(CATALOGUE.keys())
