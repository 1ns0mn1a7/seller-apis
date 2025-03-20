# Обновление остатков и цен товаров на Ozon и Яндекс Маркете

## Ozon (seller.py)

Это программа, которая помогает управлять товарами в твоем магазине на Ozon. 
Она сама обновляет цены и количество часов, чтобы в магазине всегда были актуальные данные. 
Всё, что нужно для этого, программа берет с сайта Casio и загружает на Ozon. 
Тебе не придется ничего делать вручную — она сама разберется.

Программа сначала смотрит, какие товары уже есть в твоем магазине на Ozon. 
Потом заходит на сайт Casio, скачивает файл с информацией о том, сколько часов в наличии и сколько они стоят. 
После этого она сравнивает данные и обновляет твой магазин: ставит правильное количество часов и актуальные цены. 
Если каких-то часов нет на складе Casio, она обнулит их количество на Ozon.

Чтобы всё работало, нужны специальные ключи от Ozon — их можно взять в личном кабинете продавца. 
Программа умеет обрабатывать много товаров сразу, но делает это частями, чтобы не перегружать систему. 
Если что-то пойдет не так, например, интернет пропадет или сайт не ответит, она сообщит об ошибке.

## Яндекс Маркет (market.py)

Это программа, которая помогает управлять товарами в твоем магазине на Яндекс Маркете. 
Она автоматически обновляет количество часов и их цены, чтобы в магазине всегда были актуальные данные. 
Всё, что нужно для работы, программа берет из твоей системы учета товаров и загружает на Яндекс Маркет. 
Тебе не придется обновлять ничего вручную — она сделает всё сама.

Программа сначала проверяет, какие товары уже есть в твоем магазине на Яндекс Маркете. 
Затем она берет данные о наличии и ценах часов из твоей системы учета. 
После этого сравнивает информацию и обновляет магазин: выставляет правильное количество часов и актуальные цены. 
Если каких-то часов нет в наличии, она обнулит их количество на Яндекс Маркете.

Скрипт работает с двумя моделями продаж: FBS (ты хранишь и упаковываешь товары, а Яндекс доставляет) и DBS (ты делаешь всё сам, включая доставку). 
Он обновляет данные для обеих моделей, чтобы всё было синхронизировано. 
Для работы нужны специальные ключи от Яндекс Маркета — их можно взять в личном кабинете продавца.

Программа обрабатывает много товаров сразу, но делает это частями, чтобы не перегружать систему. 
Если что-то пойдет не так — например, пропадет интернет или сервер не ответит, — она сообщит об ошибке, чтобы ты знал, что проверить.