"""What a picture asked in Spanish, French or Portuguese may be of.

``gen_intent_drawable`` reads these. A subject draws only when each of its nouns ("un
gato con sombrero en la playa") is one of these concrete things: animals, people and
roles, creatures, objects, vehicles, buildings and places, nature and weather, food,
plants, sky, toys and instruments. Its other words are ``gen_intent_drawable_words``.

Left out on purpose, even where they could be drawn: tables, plans, maps, charts,
diagrams, stories, letters, cells, hearts, skeletons, pyramids, systems, cycles, the
future, life; words with a homework or figurative sense ("planta" is also a floor plan,
"rayo" a ray of light, "hoja" a sheet, "batería" a battery, "lentes" lenses, "espejo" an
optics mirror, "tour" an overview, "champ" a field).

Notation: "gato+s" is "gato" and "gatos"; "león/leones" lists forms; "_" joins the
words of one name ("caballito_de_mar"). Accents are optional when matched.
"""

from __future__ import annotations

SPANISH = """
gato+s gatito+s gata+s perro+s perrito+s cachorro+s perra+s caballo+s potro+s poni+s pony
vaca+s toro+s cerdo+s cerdito+s chancho+s oveja+s cordero+s cabra+s gallina+s gallo+s
pollito+s pato+s patito+s ganso+s pavo+s conejo+s conejito+s liebre+s ratón/ratones
ratoncito+s rata+s hámster+s ardilla+s zorro+s lobo+s oso+s osito+s panda+s koala+s
león/leones leona+s tigre+s leopardo+s guepardo+s jaguar+es pantera+s elefante+s jirafa+s
cebra+s mono+s gorila+s chimpancé+s hipopótamo+s rinoceronte+s camello+s llama+s alpaca+s
canguro+s ciervo+s venado+s reno+s alce+s burro+s búho+s lechuza+s águila+s halcón/halcones
loro+s pingüino+s flamenco+s cisne+s pájaro+s pajarito+s ave+s cuervo+s paloma+s
gorrión/gorriones tucán/tucanes colibrí+es gaviota+s mariposa+s abeja+s mariquita+s
libélula+s araña+s hormiga+s caracol+es oruga+s rana+s sapo+s tortuga+s serpiente+s culebra+s
cocodrilo+s lagarto+s lagartija+s camaleón/camaleones iguana+s pez/peces pececito+s
tiburón/tiburones ballena+s delfín/delfines pulpo+s calamar+es medusa+s cangrejo+s langosta+s
caballito_de_mar estrella_de_mar foca+s nutria+s castor+es erizo+s murciélago+s mapache+s
perezoso+s mascota+s animal+es dinosaurio+s
dragón/dragones unicornio+s hada+s sirena+s elfo+s enano+s gnomo+s gigante+s duende+s ogro+s
mago+s bruja+s brujo+s hechicero+s fantasma+s vampiro+s zombi+s zombie+s momia+s monstruo+s
extraterrestre+s alienígena+s marciano+s robot+s fénix grifo+s pegaso+s centauro+s ángel+es
superhéroe+s superheroína+s ninja+s pirata+s caballero+s samurái+s vikingo+s vaquero+s
niña+s niño+s chica+s chico+s bebé+s mujer+es hombre+s señora+s señor+es anciano+s anciana+s
abuela+s abuelo+s joven/jóvenes rey+es reina+s príncipe+s princesa+s emperador+es guerrero+s
guerrera+s soldado+s astronauta+s piloto+s marinero+s capitán/capitanes bombero+s policía+s
médico+s doctora+s enfermera+s cocinero+s cocinera+s granjero+s pescador+es científico+s
científica+s pintor+es pintora+s músico+s cantante+s bailarín/bailarines bailarina+s payaso+s
detective+s explorador+es exploradora+s futbolista+s muñeco_de_nieve muñecos_de_nieve
espantapájaros papá_noel muñeco+s muñeca+s
sombrero+s gorro+s gorra+s corona+s paraguas sombrilla+s silla+s sofá+s cama+s lámpara+s
vela+s farol+es taza+s tetera+s jarrón/jarrones botella+s cesta+s canasta+s regalo+s globo+s
cometa+s pelota+s balón/balones juguete+s espada+s escudo+s anillo+s collar+es zapato+s bota+s
vestido+s bufanda+s gafas mochila+s maleta+s cámara+s bandera+s trofeo+s medalla+s diamante+s
joya+s máscara+s varita+s escoba+s caldero+s campana+s pluma+s concha+s caracola+s peluche+s
osito_de_peluche marioneta+s títere+s peonza+s trompo+s
coche+s carro+s auto+s camión/camiones autobús/autobuses tren+es tranvía+s taxi+s
avión/aviones avioneta+s helicóptero+s barco+s barquito+s velero+s yate+s canoa+s bote+s
submarino+s cohete+s nave_espacial naves_espaciales ovni+s bicicleta+s bici+s moto+s
motocicleta+s patinete+s monopatín/monopatines tractor+es ambulancia+s carruaje+s trineo+s
casa+s casita+s cabaña+s choza+s castillo+s palacio+s torre+s faro+s puente+s iglesia+s
catedral+es templo+s mezquita+s molino+s granero+s granja+s iglú+s rascacielos ciudad+es
pueblo+s aldea+s playa+s bosque+s selva+s jungla+s desierto+s isla+s lago+s río+s cascada+s
océano+s mar+es montaña+s volcán/volcanes valle+s cueva+s prado+s jardín/jardines parque+s
paisaje+s cañón/cañones acantilado+s costa+s puerto+s ruinas zoológico+s zoo+s acuario+s
circo+s estadio+s piscina+s
atardecer+es amanecer+es puesta_de_sol puestas_de_sol arcoíris arco_iris nube+s lluvia+s
nieve tormenta+s relámpago+s tornado+s huracán/huracanes cielo+s aurora+s árbol+es arbolito+s
palmera+s pino+s roble+s flor+es florecita+s rosa+s girasol+es tulipán/tulipanes margarita+s
lirio+s loto+s orquídea+s cactus seta+s hongo+s luna+s sol+es estrella+s planeta+s galaxia+s
nebulosa+s copo_de_nieve copos_de_nieve iceberg+s
pizza+s hamburguesa+s sándwich+es bocadillo+s sushi taco+s tarta+s pastel+es torta+s
magdalena+s galleta+s dona+s donut+s rosquilla+s helado+s chocolate+s caramelo+s piruleta+s
cruasán/cruasanes croissant+s pan+es manzana+s plátano+s banana+s naranja+s fresa+s
frutilla+s cereza+s uva+s sandía+s piña+s limón/limones pera+s melocotón/melocotones
durazno+s aguacate+s palta+s zanahoria+s tomate+s calabaza+s queso+s fruta+s café+s
guitarra+s piano+s violín/violines violonchelo+s chelo+s tambor+es trompeta+s flauta+s arpa+s
saxofón/saxofones acordeón/acordeones ukelele+s xilófono+s pandereta+s
roca+s rama+s espacio
ala+s
"""

FRENCH = """
chat+s chaton+s chatte+s chien+s chiot+s chienne+s cheval/chevaux poulain+s poney+s vache+s
taureau+x cochon+s porcelet+s mouton+s agneau+x chèvre+s poule+s coq+s poussin+s canard+s
caneton+s oie+s dinde+s lapin+s lapereau+x lièvre+s souris rat+s hamster+s écureuil+s renard+s
loup+s ours ourson+s panda+s koala+s lion+s lionne+s tigre+s léopard+s guépard+s jaguar+s
panthère+s éléphant+s girafe+s zèbre+s singe+s gorille+s chimpanzé+s hippopotame+s rhinocéros
chameau+x dromadaire+s lama+s alpaga+s kangourou+s cerf+s biche+s renne+s âne+s hibou+x
chouette+s aigle+s faucon+s perroquet+s pingouin+s manchot+s flamant+s cygne+s paon+s
oiseau+x corbeau+x colombe+s pigeon+s moineau+x toucan+s colibri+s mouette+s papillon+s
abeille+s coccinelle+s libellule+s araignée+s fourmi+s escargot+s chenille+s grenouille+s
crapaud+s tortue+s serpent+s crocodile+s alligator+s lézard+s caméléon+s iguane+s poisson+s
requin+s baleine+s dauphin+s pieuvre+s poulpe+s calmar+s méduse+s crabe+s homard+s
étoile_de_mer phoque+s loutre+s castor+s hérisson+s chauve-souris raton_laveur paresseux
animal/animaux dinosaure+s
dragon+s licorne+s fée+s sirène+s elfe+s nain+s gnome+s géant+s lutin+s gobelin+s ogre+s
sorcier+s sorcière+s magicien+s magicienne+s fantôme+s vampire+s loup-garou/loups-garous
zombie+s momie+s monstre+s extraterrestre+s martien+s robot+s phénix griffon+s centaure+s
ange+s super-héros superhéros super-héroïne ninja+s pirate+s chevalier+s samouraï+s viking+s
cowboy+s
fille+s fillette+s garçon+s enfant+s bébé+s femme+s homme+s dame+s vieillard+s grand-mère
grand-père mamie papi roi+s reine+s prince+s princesse+s empereur+s guerrier+s guerrière+s
soldat+s astronaute+s pilote+s marin+s capitaine+s pompier+s policier+s policière+s médecin+s
docteur+s infirmière+s infirmier+s cuisinier+s cuisinière+s fermier+s fermière+s pêcheur+s
scientifique+s peintre+s musicien+s musicienne+s chanteur+s chanteuse+s danseur+s danseuse+s
ballerine+s clown+s détective+s explorateur+s exploratrice+s footballeur+s personnage+s
bonhomme_de_neige père_noël épouvantail+s poupée+s
chapeau+x casquette+s bonnet+s couronne+s parapluie+s chaise+s fauteuil+s canapé+s lit+s
lampe+s bougie+s lanterne+s tasse+s théière+s vase+s bouteille+s panier+s cadeau+x ballon+s
cerf-volant/cerfs-volants balle+s jouet+s épée+s bouclier+s bague+s collier+s chaussure+s
botte+s robe+s écharpe+s lunettes sac_à_dos valise+s appareil_photo drapeau+x trophée+s
médaille+s diamant+s bijou+x masque+s baguette_magique balai+s chaudron+s cloche+s plume+s
coquillage+s nounours peluche+s marionnette+s toupie+s
voiture+s camion+s bus autobus train+s tramway+s taxi+s avion+s hélicoptère+s bateau+x
navire+s voilier+s yacht+s canoë+s barque+s sous-marin+s fusée+s vaisseau_spatial
vaisseaux_spatiaux ovni+s soucoupe_volante vélo+s bicyclette+s moto+s scooter+s trottinette+s
tracteur+s ambulance+s carrosse+s calèche+s traîneau+x montgolfière+s
maison+s maisonnette+s cabane+s chalet+s hutte+s château+x palais phare+s pont+s église+s
cathédrale+s temple+s mosquée+s moulin+s grange+s ferme+s igloo+s tente+s gratte-ciel ville+s
village+s plage+s forêt+s jungle+s désert+s île+s lac+s rivière+s fleuve+s cascade+s océan+s
mer+s montagne+s volcan+s vallée+s grotte+s caverne+s prairie+s jardin+s parc+s paysage+s
canyon+s falaise+s port+s ruines zoo+s aquarium+s cirque+s stade+s piscine+s
coucher_de_soleil couchers_de_soleil lever_de_soleil arc-en-ciel/arcs-en-ciel nuage+s pluie+s
neige orage+s éclair+s tornade+s ouragan+s ciel/cieux aurore+s arbre+s palmier+s sapin+s pin+s
chêne+s fleur+s rose+s tournesol+s tulipe+s marguerite+s lys lotus orchidée+s cactus
champignon+s lune+s soleil+s étoile+s planète+s comète+s galaxie+s nébuleuse+s flocon+s
flocon_de_neige flocons_de_neige iceberg+s
pizza+s hamburger+s burger+s sandwich+s sushi+s taco+s gâteau+x cupcake+s cookie+s biscuit+s
beignet+s donut+s glace+s chocolat+s bonbon+s sucette+s croissant+s baguette+s pain+s tarte+s
crêpe+s pomme+s banane+s orange+s fraise+s cerise+s raisin+s pastèque+s ananas citron+s poire+s
pêche+s avocat+s carotte+s tomate+s citrouille+s fromage+s fruit+s café+s
guitare+s piano+s violon+s violoncelle+s tambour+s trompette+s flûte+s harpe+s saxophone+s
accordéon+s ukulélé+s xylophone+s tambourin+s
branche+s espace coucher_du_soleil
aile+s tempête+s
"""

PORTUGUESE = """
gato+s gatinho+s gata+s cachorro+s cachorrinho+s cão/cães cadela+s filhote+s cavalo+s potro+s
pônei+s vaca+s touro+s porco+s porquinho+s ovelha+s cordeiro+s cabra+s galinha+s galo+s
pintinho+s pato+s patinho+s ganso+s coelho+s coelhinho+s lebre+s rato+s ratinho+s hamster+s
esquilo+s raposa+s lobo+s urso+s ursinho+s panda+s coala+s leão/leões leoa+s tigre+s
leopardo+s guepardo+s onça+s pantera+s elefante+s girafa+s zebra+s macaco+s gorila+s
chimpanzé+s hipopótamo+s rinoceronte+s camelo+s lhama+s alpaca+s canguru+s cervo+s rena+s
alce+s burro+s jumento+s coruja+s águia+s falcão/falcões papagaio+s pinguim/pinguins
flamingo+s cisne+s pavão/pavões pássaro+s passarinho+s ave+s corvo+s pomba+s pardal/pardais
tucano+s beija-flor/beija-flores gaivota+s borboleta+s abelha+s joaninha+s libélula+s aranha+s
formiga+s caracol/caracóis lagarta+s sapo+s rã+s tartaruga+s cobra+s serpente+s crocodilo+s
jacaré+s lagarto+s lagartixa+s camaleão/camaleões iguana+s peixe+s peixinho+s
tubarão/tubarões baleia+s golfinho+s polvo+s lula+s água-viva caranguejo+s lagosta+s
cavalo-marinho estrela-do-mar foca+s lontra+s castor+es ouriço+s morcego+s
guaxinim/guaxinins preguiça+s animal/animais dinossauro+s bicho+s
dragão/dragões unicórnio+s fada+s sereia+s elfo+s anão/anões gnomo+s gigante+s duende+s ogro+s
mago+s bruxa+s bruxo+s feiticeiro+s fantasma+s vampiro+s lobisomem/lobisomens zumbi+s
zombie+s múmia+s monstro+s monstrinho+s alienígena+s extraterrestre+s marciano+s robô+s robo
fênix grifo+s centauro+s anjo+s super-herói/super-heróis super-heroína+s ninja+s pirata+s
cavaleiro+s samurai+s viking+s caubói+s cowboy+s
menina+s menino+s garota+s garoto+s criança+s bebê+s mulher+es homem/homens senhora+s
senhor+es idoso+s idosa+s avó+s avô+s vovó vovô rei+s rainha+s príncipe+s princesa+s
imperador+es guerreiro+s guerreira+s soldado+s astronauta+s piloto+s marinheiro+s
capitão/capitães bombeiro+s policial/policiais médico+s médica+s enfermeira+s enfermeiro+s
cozinheiro+s cozinheira+s fazendeiro+s pescador+es cientista+s pintor+es músico+s cantor+es
cantora+s dançarino+s dançarina+s bailarina+s palhaço+s detetive+s explorador+es jogador+es
personagem/personagens boneco_de_neve bonecos_de_neve papai_noel espantalho+s boneca+s
boneco+s
chapéu+s boné+s gorro+s coroa+s guarda-chuva+s cadeira+s poltrona+s sofá+s cama+s abajur
vela+s lanterna+s xícara+s caneca+s bule+s garrafa+s cesta+s balão/balões pipa+s bola+s
brinquedo+s espada+s escudo+s anel/anéis colar+es sapato+s bota+s vestido+s cachecol óculos
mochila+s mala+s câmera+s bandeira+s troféu+s medalha+s diamante+s joia+s máscara+s varinha+s
vassoura+s caldeirão sino+s concha+s pelúcia+s marionete+s fantoche+s pião/piões
carro+s carrinho+s automóvel/automóveis caminhão/caminhões ônibus trem/trens bonde+s táxi+s
avião/aviões helicóptero+s barco+s navio+s veleiro+s iate+s canoa+s submarino+s foguete+s
nave_espacial naves_espaciais disco_voador óvni bicicleta+s bike+s moto+s motocicleta+s
patinete+s skate+s trator+es ambulância+s carruagem/carruagens trenó+s
casa+s casinha+s cabana+s chalé+s castelo+s palácio+s torre+s farol/faróis ponte+s igreja+s
catedral/catedrais templo+s mesquita+s moinho+s celeiro+s fazenda+s iglu+s barraca+s
arranha-céu/arranha-céus cidade+s vila+s aldeia+s praia+s floresta+s selva+s deserto+s ilha+s
lago+s rio+s cachoeira+s cascata+s oceano+s mar+es montanha+s vulcão/vulcões vale+s
caverna+s gruta+s prado+s jardim/jardins parque+s paisagem/paisagens falésia+s porto+s ruínas
zoológico+s aquário+s circo+s estádio+s piscina+s
pôr_do_sol pores_do_sol nascer_do_sol arco-íris nuvem/nuvens chuva+s neve tempestade+s
relâmpago+s tornado+s furacão/furacões céu+s aurora+s árvore+s palmeira+s pinheiro+s
carvalho+s flor+es florzinha rosa+s girassol/girassóis tulipa+s margarida+s lírio+s lótus
orquídea+s cacto+s cogumelo+s lua+s sol/sóis estrela+s planeta+s cometa+s galáxia+s nebulosa+s
floco_de_neve flocos_de_neve iceberg+s
pizza+s hambúrguer+es sanduíche+s sushi taco+s bolo+s cupcake+s biscoito+s bolacha+s
rosquinha+s donut+s sorvete+s chocolate+s bombom/bombons pirulito+s croissant+s pão/pães
torta+s panqueca+s maçã+s banana+s laranja+s morango+s cereja+s uva+s melancia+s abacaxi+s
limão/limões pera+s pêssego+s abacate+s cenoura+s tomate+s abóbora+s queijo+s fruta+s café+s
violão/violões guitarra+s piano+s violino+s violoncelo+s tambor+es trompete+s flauta+s harpa+s
saxofone+s acordeão/acordeões sanfona+s ukulele+s xilofone+s pandeiro+s
galho+s espaço areia
asa+s
"""
