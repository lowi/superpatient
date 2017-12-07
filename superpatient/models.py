#    Copyright 2006-2017 Tibor Csernay

#    This file is part of SuperPatient.

#    SuperPatient is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.

#    SuperPatient is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.

#    You should have received a copy of the GNU General Public License
#    along with SuperPatient; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

OLD_PAYMENT_METHODS = [u'CdM']
PAYMENT_METHODS = [u'Cash', u'Carte', u'BVR', u'Dû', u'PVPE']
PAYMENT_STATUSES = [u'Tous', u'Comptabilisé', u'Non-comptabilisé']

BILL_STATUSES = [u'Tous', u'Ouverte', u'Imprimée', u'Envoyée', u'Payée', u'Abandonnée']
STATUS_OPENED = u'O'
STATUS_PRINTED = u'I'
STATUS_SENT = u'E'
STATUS_PAYED = u'P'
STATUS_ABANDONED = u'A'


class Model(object):
    TABLE = None
    FIELDS = []
    EXTRA_FIELDS = []

    @classmethod
    def load(klass, cursor, key):
        cursor.execute("""SELECT %s FROM %s WHERE %s=%%s"""
                       % (', '.join(klass.FIELDS),
                          klass.TABLE,
                          klass.FIELDS[0]),
                       [key])
        data = cursor.fetchone()
        fields = {}
        for extra in klass.EXTRA_FIELDS:
            fields[extra] = None
        fields.update(dict(zip(klass.FIELDS, data)))
        return klass(**fields)

    @classmethod
    def yield_all(klass, cursor, where=None, order=None):
        where_cond = []
        where_args = []
        if where is not None:
            for key, value in where.items():
                if '__' in key:
                    field, test = key.split('__')
                else:
                    field, test = key, 'eq'
                test = {'eq': '=',
                        'gt': '>',
                        'lt': '<',
                        'ge': '>=',
                        'le': '<=',
                        'like': 'LIKE',
                        'ilike': 'ILIKE',
                        }[test]
                where_cond.append('%s %s %%s' % (field, test))
                where_args.append(value)
            where = 'WHERE ' + ' AND '.join(where_cond)
        else:
            where = ''
        if order is not None:
            field, direction = order, 'ASC'
            if order[0] == '-':
                field, direction = order[1:], 'DESC'
            order = 'ORDER BY %s %s' % (field, direction)
        else:
            order = ''
        cursor.execute("SELECT %s FROM %s %s %s"
                       % (', '.join(klass.FIELDS),
                          klass.TABLE,
                          where,
                          order),
                       where_args)
        for data in cursor:
            yield klass(**dict(zip(klass.FIELDS, data)))

    def __init__(self, **kwds):
        for field in self.FIELDS + self.EXTRA_FIELDS:
            setattr(self, field, kwds.pop(field, None))
        if kwds:
            raise TypeError("extraneous parameters %s" % ', '.join("`%s'" % k for k in kwds))

    def __bool__(self):
        # True if this model already has a key
        return getattr(self, self.FIELDS[0]) is not None

    def __setattr__(self, field, value):
        if field not in self.FIELDS + self.EXTRA_FIELDS:
            raise AttributeError("unknown attribute `%s'" % field)
        super(Model, self).__setattr__(field, value)

    def save(self, cursor):
        if not self:
            cursor.execute("""SELECT max(%s)+1 FROM %s""" % (self.FIELDS[0], self.TABLE))
            key, = cursor.fetchone()
            if key is None:
                key = 1
            setattr(self, self.FIELDS[0], key)
            cursor.execute("""INSERT INTO %s (%s) VALUES (%s)"""
                           % (self.TABLE,
                              ', '.join(self.FIELDS),
                              ', '.join(['%s'] * len(self.FIELDS))),
                           [getattr(self, field) for field in self.FIELDS])
        else:
            cursor.execute("""UPDATE %s SET %s WHERE %s=%%s"""
                           % (self.TABLE,
                              ', '.join('%s=%%s' % f for f in self.FIELDS[1:]),
                              self.FIELDS[0]),
                           [getattr(self, field) for field in self.FIELDS[1:]] + [getattr(self, self.FIELDS[0])])


class Patient(Model):
    TABLE = 'patients'
    FIELDS = ['id', 'date_ouverture', 'therapeute', 'sex', 'nom', 'prenom',
              'date_naiss', 'ATCD_perso', 'ATCD_fam', 'medecin',
              'autre_medecin', 'phone', 'portable', 'profes_phone', 'mail',
              'adresse', 'ass_compl', 'profes', 'etat', 'envoye', 'divers',
              'important']


class Consultation(Model):
    TABLE = 'consultations'
    FIELDS = ['id_consult', 'id', 'date_consult', 'heure_consult', 'MC', 'MC_accident', 'EG',
              'exam_pclin', 'exam_phys', 'paye', 'divers', 'APT_thorax',
              'APT_abdomen', 'APT_tete', 'APT_MS', 'APT_MI', 'APT_system',
              'A_osteo', 'traitement', 'therapeute', 'prix_cts', 'prix_txt',
              'majoration_cts', 'majoration_txt', 'frais_admin_cts', 'frais_admin_txt',
              'paye_par', 'paye_le', 'bv_ref', 'status']
    EXTRA_FIELDS = ['patient', 'rappel_cts']

    @classmethod
    def load(klass, cursor, key):
        instance = super(Consultation, klass).load(cursor, key)
        instance.patient = Patient.load(cursor, instance.id)
        cursor.execute("""SELECT sum(rappel_cts) FROM rappels WHERE id_consult=%s""", [key])
        if cursor.rowcount:
            instance.rappel_cts, = cursor.fetchone()
        if instance.rappel_cts is None:
            instance.rappel_cts = 0
        if instance.therapeute is None:
            instance.therapeute = instance.patient.therapeute
        return instance

    def __init__(self, **kwds):
        super(Consultation, self).__init__(**kwds)
        self.rappel_cts = 0